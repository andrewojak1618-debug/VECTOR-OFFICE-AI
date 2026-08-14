import os
import unittest
from unittest.mock import patch

from config.settings import get_bool_setting


class SettingsTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
