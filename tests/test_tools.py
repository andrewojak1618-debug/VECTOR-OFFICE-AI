"""Security and integration tests for the controlled tool registry."""

import unittest

from brain.agent import Agent
from tests.test_agent import RecordingLanguageModel
from tools.permissions import PermissionLevel, ToolAuthorization
from tools.registry import (
    REDACTED_ARGUMENT,
    ToolDefinition,
    ToolExecutionResult,
    ToolParameter,
    ToolParameterType,
    ToolRegistry,
    ToolResultStatus,
)
from tools.test_tools import EchoTestTool


class RecordingTool:
    def __init__(self, name: str, permission: PermissionLevel, fail: bool = False):
        self._definition = ToolDefinition(name, "Test operation.", permission)
        self.fail = fail
        self.calls = 0

    @property
    def definition(self):
        return self._definition

    def execute(self, arguments):
        self.calls += 1
        if self.fail:
            raise RuntimeError("secret internal failure")
        return {"calls": self.calls}


class ToolRegistryTests(unittest.TestCase):
    def test_registered_read_only_tool_returns_structured_result(self):
        registry = ToolRegistry()
        registry.register(EchoTestTool())

        result = registry.execute("test.echo", {"text": "Hallo"})

        self.assertIsInstance(result, ToolExecutionResult)
        self.assertTrue(result.succeeded)
        self.assertEqual(ToolResultStatus.SUCCESS, result.status)
        self.assertEqual("Hallo", result.output["echo"])

    def test_definition_exposes_description_and_parameter_schema(self):
        registry = ToolRegistry()
        registry.register(EchoTestTool())

        definition = registry.definitions()[0]

        self.assertEqual("test.echo", definition.name)
        self.assertEqual(PermissionLevel.READ_ONLY, definition.permission)
        self.assertEqual(["text", "secret"], [item.name for item in definition.parameters])
        self.assertTrue(definition.parameters[1].sensitive)

    def test_sensitive_parameters_are_redacted_from_audit_events(self):
        events = []
        registry = ToolRegistry(audit_sink=events.append)
        registry.register(EchoTestTool())
        secret = "sensitive-test-value"

        result = registry.execute(
            "test.echo",
            {"text": "sichtbar", "secret": secret},
        )

        self.assertTrue(result.succeeded)
        self.assertEqual(REDACTED_ARGUMENT, events[0].arguments["secret"])
        self.assertNotIn(secret, repr(events[0]))
        self.assertNotIn("secret", result.output)

    def test_unregistered_tool_is_blocked_without_auditing_arguments(self):
        events = []
        registry = ToolRegistry(audit_sink=events.append)

        result = registry.execute("unknown.tool", {"secret": "do-not-log"})

        self.assertEqual(ToolResultStatus.BLOCKED, result.status)
        self.assertEqual("tool_not_registered", result.error_code)
        self.assertEqual({}, dict(events[0].arguments))
        self.assertNotIn("do-not-log", repr(events[0]))

    def test_unsafe_requested_name_cannot_alias_a_registered_tool(self):
        tool = RecordingTool("invalid-tool-name", PermissionLevel.READ_ONLY)
        registry = ToolRegistry()
        registry.register(tool)

        result = registry.execute("INVALID TOOL NAME", {})

        self.assertEqual(ToolResultStatus.BLOCKED, result.status)
        self.assertEqual(0, tool.calls)

    def test_invalid_parameters_are_blocked_before_tool_execution(self):
        tool = EchoTestTool()
        registry = ToolRegistry()
        registry.register(tool)

        results = (
            registry.execute("test.echo", {}),
            registry.execute("test.echo", {"text": 12}),
            registry.execute("test.echo", {"text": "ok", "extra": True}),
        )

        self.assertTrue(all(item.status is ToolResultStatus.INVALID for item in results))

    def test_mutating_tool_requires_explicit_mutation_authority(self):
        tool = RecordingTool("test.write", PermissionLevel.MUTATING)
        registry = ToolRegistry()
        registry.register(tool)

        blocked = registry.execute("test.write", {})
        allowed = registry.execute(
            "test.write",
            {},
            ToolAuthorization(allow_mutation=True),
        )

        self.assertEqual("mutation_not_allowed", blocked.error_code)
        self.assertTrue(allowed.succeeded)
        self.assertEqual(1, tool.calls)

    def test_dangerous_tool_always_requires_per_call_confirmation(self):
        tool = RecordingTool("test.danger", PermissionLevel.DANGEROUS)
        registry = ToolRegistry()
        registry.register(tool)
        mutation_only = ToolAuthorization(allow_mutation=True)
        confirmed = ToolAuthorization(allow_mutation=True, confirmed=True)

        blocked = registry.execute("test.danger", {}, mutation_only)
        allowed = registry.execute("test.danger", {}, confirmed)

        self.assertEqual("confirmation_required", blocked.error_code)
        self.assertTrue(allowed.succeeded)
        self.assertEqual(1, tool.calls)

    def test_registered_permission_cannot_be_lowered_by_mutable_tool_metadata(self):
        tool = RecordingTool("test.fixed", PermissionLevel.DANGEROUS)
        registry = ToolRegistry()
        registry.register(tool)
        tool._definition = ToolDefinition(
            "test.fixed",
            "Changed metadata.",
            PermissionLevel.READ_ONLY,
        )

        result = registry.execute("test.fixed", {})

        self.assertEqual("mutation_not_allowed", result.error_code)
        self.assertEqual(0, tool.calls)

    def test_tool_failures_return_sanitized_structured_errors(self):
        tool = RecordingTool("test.failure", PermissionLevel.READ_ONLY, fail=True)
        registry = ToolRegistry()
        registry.register(tool)

        result = registry.execute("test.failure", {})

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual("tool_execution_failed", result.error_code)
        self.assertNotIn("secret internal failure", result.message)

    def test_agent_receives_registry_result_without_automatic_model_execution(self):
        registry = ToolRegistry()
        registry.register(EchoTestTool())
        model = RecordingLanguageModel("Nicht verwendet")
        agent = Agent(model, tool_registry=registry)

        result = agent.execute_tool("test.echo", {"text": "Agent result"})

        self.assertEqual("Agent result", result.output["echo"])
        self.assertEqual(0, len(model.received_messages))

    def test_agent_without_registry_blocks_tool_calls(self):
        agent = Agent(RecordingLanguageModel("Nicht verwendet"))

        result = agent.execute_tool("test.echo", {"text": "blocked"})

        self.assertEqual(ToolResultStatus.BLOCKED, result.status)
        self.assertEqual("tool_registry_unavailable", result.error_code)

    def test_duplicate_registration_is_rejected(self):
        registry = ToolRegistry()
        registry.register(EchoTestTool())

        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register(EchoTestTool())

    def test_parameter_definition_rejects_unsafe_names(self):
        with self.assertRaisesRegex(ValueError, "safe characters"):
            ToolParameter(
                "Unsafe Name",
                "Invalid parameter.",
                ToolParameterType.STRING,
            )

    def test_authorization_rejects_non_boolean_flags(self):
        with self.assertRaisesRegex(TypeError, "boolean"):
            ToolAuthorization(allow_mutation="yes")

    def test_non_finite_number_is_rejected_before_execution(self):
        definition = ToolDefinition(
            "test.number",
            "Validate a finite number.",
            PermissionLevel.READ_ONLY,
            (ToolParameter("value", "Finite value.", ToolParameterType.NUMBER),),
        )
        tool = RecordingTool("test.number", PermissionLevel.READ_ONLY)
        tool._definition = definition
        registry = ToolRegistry()
        registry.register(tool)

        result = registry.execute("test.number", {"value": float("nan")})

        self.assertEqual(ToolResultStatus.INVALID, result.status)
        self.assertEqual(0, tool.calls)


if __name__ == "__main__":
    unittest.main()
