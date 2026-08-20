"""Tests for deterministic read-only local office tools."""

import unittest
from datetime import datetime, timedelta, timezone

from tools.office import LocalDateTimeTool, register_office_tools
from tools.permissions import PermissionLevel
from tools.registry import ToolRegistry, ToolResultStatus


TEST_TIMEZONE = timezone(timedelta(hours=2), "CEST")
TEST_NOW = datetime(2026, 8, 20, 14, 5, tzinfo=TEST_TIMEZONE)


class LocalDateTimeToolTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        register_office_tools(self.registry, lambda: TEST_NOW)

    def test_definition_is_read_only_and_accepts_only_mode_parameter(self):
        definition = self.registry.definitions()[0]

        self.assertEqual("office.local_datetime", definition.name)
        self.assertEqual(PermissionLevel.READ_ONLY, definition.permission)
        self.assertEqual(("mode",), tuple(item.name for item in definition.parameters))

    def test_time_is_formatted_locally_without_authorization(self):
        result = self.registry.execute(
            "office.local_datetime",
            {"mode": "time"},
        )

        self.assertTrue(result.succeeded)
        self.assertEqual("14:05", result.output["time"])
        self.assertEqual("Es ist 14 Uhr 5.", result.output["spoken_text"])

    def test_date_uses_fixed_german_names_without_system_locale(self):
        result = self.registry.execute(
            "office.local_datetime",
            {"mode": "date"},
        )

        self.assertTrue(result.succeeded)
        self.assertEqual("2026-08-20", result.output["date"])
        self.assertEqual(
            "Heute ist Donnerstag, der 20. August 2026.",
            result.output["spoken_text"],
        )

    def test_unknown_mode_fails_with_sanitized_registry_result(self):
        result = self.registry.execute(
            "office.local_datetime",
            {"mode": "secret"},
        )

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual({}, dict(result.output))

    def test_invalid_clock_result_never_escapes_registry(self):
        tool = LocalDateTimeTool(lambda: "not-a-datetime")
        registry = ToolRegistry()
        registry.register(tool)

        result = registry.execute("office.local_datetime", {"mode": "date"})

        self.assertEqual(ToolResultStatus.FAILED, result.status)


if __name__ == "__main__":
    unittest.main()
