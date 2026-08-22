import os
import unittest
from unittest.mock import patch

from config.settings import (
    DEFAULT_EMBEDDING_PROVIDER,
    DEFAULT_DIAGNOSTICS_ENABLED,
    DEFAULT_DIAGNOSTICS_MAX_BYTES,
    DEFAULT_KNOWLEDGE_ALLOW_CLOUD,
    DEFAULT_TOOL_AUDIT_ENABLED,
    DEFAULT_TOOL_AUDIT_MAX_ENTRIES,
    DEFAULT_TOOL_AUDIT_RETENTION_DAYS,
    get_bool_setting,
    get_float_setting,
    get_int_setting,
)
from config.environment import (
    get_bool_setting as environment_bool_setting,
    get_float_setting as environment_float_setting,
    get_int_setting as environment_int_setting,
)


class SettingsTests(unittest.TestCase):
    def test_setting_helpers_keep_compatible_import_paths(self):
        self.assertIs(environment_bool_setting, get_bool_setting)
        self.assertIs(environment_float_setting, get_float_setting)
        self.assertIs(environment_int_setting, get_int_setting)

    def test_privacy_defaults_keep_embeddings_local_and_cloud_knowledge_off(self):
        self.assertEqual("ollama", DEFAULT_EMBEDDING_PROVIDER)
        self.assertFalse(DEFAULT_KNOWLEDGE_ALLOW_CLOUD)

    def test_audit_defaults_are_local_enabled_and_bounded(self):
        self.assertTrue(DEFAULT_TOOL_AUDIT_ENABLED)
        self.assertEqual(30, DEFAULT_TOOL_AUDIT_RETENTION_DAYS)
        self.assertEqual(1_000, DEFAULT_TOOL_AUDIT_MAX_ENTRIES)

    def test_diagnostics_defaults_are_local_enabled_and_bounded(self):
        self.assertTrue(DEFAULT_DIAGNOSTICS_ENABLED)
        self.assertEqual(1_000_000, DEFAULT_DIAGNOSTICS_MAX_BYTES)

    def test_bool_setting_accepts_true_value(self):
        with patch.dict(os.environ, {"TEST_BOOLEAN": "true"}):
            self.assertTrue(get_bool_setting("TEST_BOOLEAN", False))

    def test_bool_setting_accepts_false_value(self):
        with patch.dict(os.environ, {"TEST_BOOLEAN": "off"}):
            self.assertFalse(get_bool_setting("TEST_BOOLEAN", True))

    def test_bool_setting_uses_default_when_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(get_bool_setting("TEST_BOOLEAN", True))

    def test_bool_setting_rejects_unknown_value(self):
        with patch.dict(os.environ, {"TEST_BOOLEAN": "perhaps"}):
            with self.assertRaises(ValueError):
                get_bool_setting("TEST_BOOLEAN", False)

    def test_float_setting_accepts_bounded_value(self):
        with patch.dict(os.environ, {"TEST_FLOAT": "0.42"}):
            value = get_float_setting("TEST_FLOAT", 0.5, 0.0, 1.0)

        self.assertEqual(0.42, value)

    def test_float_setting_rejects_invalid_or_out_of_range_value(self):
        with patch.dict(os.environ, {"TEST_FLOAT": "invalid"}):
            with self.assertRaisesRegex(ValueError, "number"):
                get_float_setting("TEST_FLOAT", 0.5, 0.0, 1.0)
        with patch.dict(os.environ, {"TEST_FLOAT": "2.0"}):
            with self.assertRaisesRegex(ValueError, "between"):
                get_float_setting("TEST_FLOAT", 0.5, 0.0, 1.0)

    def test_provider_timeout_environment_values_are_bounded(self):
        limits = {
            "WIREPOD_REQUEST_TIMEOUT": (1.0, 30.0),
            "OPENAI_REQUEST_TIMEOUT": (1.0, 600.0),
            "OLLAMA_REQUEST_TIMEOUT": (1.0, 600.0),
            "ELEVENLABS_TIMEOUT": (1.0, 60.0),
            "OLLAMA_EMBEDDING_TIMEOUT": (1.0, 600.0),
        }
        for name, (minimum, maximum) in limits.items():
            for value in (minimum - 0.1, maximum + 0.1):
                with self.subTest(name=name, value=value), patch.dict(
                    os.environ,
                    {name: str(value)},
                ), self.assertRaisesRegex(ValueError, name):
                    get_float_setting(name, minimum, minimum, maximum)


if __name__ == "__main__":
    unittest.main()
