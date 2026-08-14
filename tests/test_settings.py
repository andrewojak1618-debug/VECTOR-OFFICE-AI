import os
import unittest
from unittest.mock import patch

from config.settings import (
    DEFAULT_EMBEDDING_PROVIDER,
    DEFAULT_KNOWLEDGE_ALLOW_CLOUD,
    get_bool_setting,
    get_float_setting,
)


class SettingsTests(unittest.TestCase):
    def test_privacy_defaults_keep_embeddings_local_and_cloud_knowledge_off(self):
        self.assertEqual("ollama", DEFAULT_EMBEDDING_PROVIDER)
        self.assertFalse(DEFAULT_KNOWLEDGE_ALLOW_CLOUD)

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


if __name__ == "__main__":
    unittest.main()
