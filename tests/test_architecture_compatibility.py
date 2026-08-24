"""Regressionstests für erhaltene Importpfade nach Modulaufteilungen."""

import unittest

import application.runtime as runtime
import application.runtime_startup as runtime_startup
import brain.agent as agent
import brain.contracts as contracts
import tools.registry as registry
import tools.registry_types as registry_types
import vector.onecore_tts as onecore_tts
import vector.speech as speech


class ArchitectureCompatibilityTests(unittest.TestCase):
    def test_runtime_keeps_startup_helper_alias(self):
        self.assertIs(runtime._ensure_ollama, runtime_startup.ensure_ollama)
        self.assertIs(runtime._connect_vector, runtime_startup.connect_vector)

    def test_agent_keeps_contract_exports(self):
        self.assertIs(agent.LanguageModel, contracts.LanguageModel)
        self.assertIs(agent.MemoryStore, contracts.MemoryStore)
        self.assertIs(agent.KnowledgeLibrary, contracts.KnowledgeLibrary)

    def test_registry_keeps_type_exports(self):
        self.assertIs(registry.ToolDefinition, registry_types.ToolDefinition)
        self.assertIs(registry.ToolParameter, registry_types.ToolParameter)
        self.assertIs(
            registry.ToolExecutionResult,
            registry_types.ToolExecutionResult,
        )
        self.assertIs(registry.ToolAuditEvent, registry_types.ToolAuditEvent)

    def test_speech_keeps_onecore_template_export(self):
        self.assertIs(
            speech.ONECORE_TTS_SCRIPT,
            onecore_tts.ONECORE_TTS_SCRIPT,
        )


if __name__ == "__main__":
    unittest.main()
