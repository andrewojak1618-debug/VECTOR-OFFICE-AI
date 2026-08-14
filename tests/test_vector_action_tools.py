import unittest
from unittest.mock import MagicMock

from tools.permissions import ToolAuthorization
from tools.registry import ToolRegistry, ToolResultStatus
from tools.vector_actions import register_vector_action_tools


class VectorActionToolTests(unittest.TestCase):
    def setUp(self):
        self.actions = MagicMock()
        self.actions.available_actions.return_value = (
            "head_up",
            "head_level",
        )
        self.actions.perform.return_value = True
        self.actions.emergency_stop.return_value = True
        self.registry = ToolRegistry()
        register_vector_action_tools(self.registry, self.actions)

    def test_runtime_registration_contains_only_reviewed_robot_tools(self):
        self.assertEqual(
            ("vector.emergency_stop", "vector.perform_action"),
            tuple(item.name for item in self.registry.definitions()),
        )

    def test_action_requires_explicit_mutation_authority(self):
        result = self.registry.execute(
            "vector.perform_action",
            {"action": "head_up"},
        )

        self.assertEqual(ToolResultStatus.BLOCKED, result.status)
        self.actions.perform.assert_not_called()

    def test_authorized_action_returns_structured_result(self):
        result = self.registry.execute(
            "vector.perform_action",
            {"action": "head_up"},
            ToolAuthorization(allow_mutation=True),
        )

        self.assertTrue(result.succeeded)
        self.assertEqual("head_up", result.output["action"])
        self.assertTrue(result.output["completed"])

    def test_non_allowlisted_action_fails_without_raw_exception(self):
        self.actions.perform.side_effect = ValueError("private details")

        result = self.registry.execute(
            "vector.perform_action",
            {"action": "drive_forward"},
            ToolAuthorization(allow_mutation=True),
        )

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual("tool_execution_failed", result.error_code)
        self.assertNotIn("private details", result.message)

    def test_emergency_stop_is_registered_and_requires_authority(self):
        blocked = self.registry.execute("vector.emergency_stop", {})
        allowed = self.registry.execute(
            "vector.emergency_stop",
            {},
            ToolAuthorization(allow_mutation=True),
        )

        self.assertEqual(ToolResultStatus.BLOCKED, blocked.status)
        self.assertTrue(allowed.succeeded)
        self.assertTrue(allowed.output["stopped"])
        self.assertTrue(allowed.output["latched"])


if __name__ == "__main__":
    unittest.main()
