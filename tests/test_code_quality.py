"""Automated guardrails derived from the project's clean-code rules."""

import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRODUCTION_PACKAGES = (
    "application",
    "brain",
    "config",
    "diagnostics",
    "memory",
    "tools",
    "vector",
    "voice",
)
# Fourteen lines remain the design target; 35 is the regression hard limit.
MAX_FUNCTION_LINES = 35
MAX_MODULE_LINES = 399
CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")
ENGLISH_DOCSTRING_PREFIXES = (
    "Build ",
    "Check ",
    "Create ",
    "Delete ",
    "Execute ",
    "Generate ",
    "Map ",
    "Parse ",
    "Read ",
    "Report ",
    "Return ",
    "Run ",
    "Speak ",
    "Start ",
    "Store ",
    "Validate ",
    "Write ",
)
ARCHITECTURE_MODULE_DOCS = {
    Path("application/runtime_startup.py"): Path("docs/architecture.md"),
    Path("application/response_delivery.py"): Path("docs/architecture.md"),
    Path("application/contextual_tool_conversation.py"): Path(
        "docs/tools-security.md"
    ),
    Path("application/host_watchdog.py"): Path("docs/windows-startup.md"),
    Path("application/process_control.py"): Path("docs/windows-startup.md"),
    Path("application/wirepod_host_service.py"): Path("docs/windows-startup.md"),
    Path("application/wirepod_preflight.py"): Path("docs/windows-startup.md"),
    Path("application/voice_recovery.py"): Path("docs/connections.md"),
    Path("application/voice_turn_loop.py"): Path("docs/voice.md"),
    Path("voice/followup_factory.py"): Path("docs/voice.md"),
    Path("voice/vosk_followup.py"): Path("docs/voice.md"),
    Path("application/expression_delivery.py"): Path("docs/robot-actions.md"),
    Path("application/expression_conversation.py"): Path("docs/robot-actions.md"),
    Path("application/model_tool_proposals.py"): Path("docs/tools-security.md"),
    Path("application/tool_conversation.py"): Path("docs/tools-security.md"),
    Path("brain/emotions.py"): Path("docs/personality.md"),
    Path("brain/contracts.py"): Path("docs/architecture.md"),
    Path("brain/expression_actions.py"): Path("docs/personality.md"),
    Path("brain/reflection.py"): Path("docs/personality.md"),
    Path("brain/fallback_provider.py"): Path("docs/architecture.md"),
    Path("brain/local_document_summary.py"): Path("docs/tools-security.md"),
    Path("brain/provider_diagnostics.py"): Path("docs/architecture.md"),
    Path("brain/response_quality.py"): Path("docs/provider-reliability.md"),
    Path("config/environment.py"): Path("docs/architecture.md"),
    Path("memory/document_text.py"): Path("docs/architecture.md"),
    Path("memory/embedding_records.py"): Path("docs/architecture.md"),
    Path("memory/embedding_schema.py"): Path("docs/architecture.md"),
    Path("memory/embedding_types.py"): Path("docs/architecture.md"),
    Path("memory/knowledge_records.py"): Path("docs/architecture.md"),
    Path("memory/knowledge_schema.py"): Path("docs/architecture.md"),
    Path("diagnostics/tool_audit.py"): Path("docs/tools-security.md"),
    Path("tools/audit_store.py"): Path("docs/tools-security.md"),
    Path("tools/changelog_status.py"): Path("docs/tools-security.md"),
    Path("tools/code_quality_status.py"): Path("docs/tools-security.md"),
    Path("tools/latest_tool_status.py"): Path("docs/tools-security.md"),
    Path("tools/registry.py"): Path("docs/progress.md"),
    Path("tools/registry_types.py"): Path("docs/tools-security.md"),
    Path("tools/inspection.py"): Path("docs/tools-security.md"),
    Path("tools/proposals.py"): Path("docs/tools-security.md"),
    Path("tools/python_release.py"): Path("docs/tools-security.md"),
    Path("tools/project_documents.py"): Path("docs/tools-security.md"),
    Path("tools/project_document_summary.py"): Path("docs/tools-security.md"),
    Path("tools/project_directories.py"): Path("docs/tools-security.md"),
    Path("tools/selection.py"): Path("docs/tools-security.md"),
    Path("tools/selection_matching.py"): Path("docs/tools-security.md"),
    Path("tools/tool_values.py"): Path("docs/architecture.md"),
    Path("vector/actions.py"): Path("README.md"),
    Path("vector/behavior_control.py"): Path("docs/robot-actions.md"),
    Path("vector/speech_prosody.py"): Path("docs/personality.md"),
    Path("vector/elevenlabs_speech.py"): Path("docs/voice.md"),
    Path("vector/onecore_tts.py"): Path("docs/voice.md"),
    Path("vector/speech_factory.py"): Path("docs/voice.md"),
}


def production_files() -> tuple[Path, ...]:
    files = [PROJECT_ROOT / "main.py"]
    for package in PRODUCTION_PACKAGES:
        files.extend((PROJECT_ROOT / package).rglob("*.py"))
    return tuple(sorted(files))


class CodeQualityTests(unittest.TestCase):
    """Prevent structural regressions that are cheap to detect statically."""

    def test_modules_describe_their_responsibility(self):
        missing = [
            str(path.relative_to(PROJECT_ROOT))
            for path in production_files()
            if ast.get_docstring(self._tree(path)) is None
        ]
        self.assertEqual([], missing)

    def test_public_apis_have_docstrings(self):
        missing = []
        for path in production_files():
            for node in ast.walk(self._tree(path)):
                if self._is_public_api(node) and ast.get_docstring(node) is None:
                    missing.append(f"{path.name}:{node.lineno}:{node.name}")
        self.assertEqual([], missing)

    def test_all_production_functions_have_docstrings(self):
        """Prüft auch private Funktionen, Methoden, Konstruktoren und Properties."""
        missing = []
        for path in production_files():
            for node in ast.walk(self._tree(path)):
                if self._is_function(node) and ast.get_docstring(node) is None:
                    relative = path.relative_to(PROJECT_ROOT)
                    missing.append(f"{relative}:{node.lineno}:{node.name}")
        self.assertEqual([], missing)

    def test_function_docstrings_do_not_use_english_template_verbs(self):
        """Blockiert die früher verwendeten englischen Standardformulierungen."""
        affected = []
        for path in production_files():
            for node in ast.walk(self._tree(path)):
                if not self._is_function(node):
                    continue
                docstring = ast.get_docstring(node) or ""
                if docstring.startswith(ENGLISH_DOCSTRING_PREFIXES):
                    relative = path.relative_to(PROJECT_ROOT)
                    affected.append(f"{relative}:{node.lineno}:{node.name}")
        self.assertEqual([], affected)

    def test_functions_stay_below_hard_size_limit(self):
        oversized = []
        for path in production_files():
            for node in ast.walk(self._tree(path)):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    lines = node.end_lineno - node.lineno + 1
                    if lines > MAX_FUNCTION_LINES:
                        oversized.append(f"{path.name}:{node.name}:{lines}")
        self.assertEqual([], oversized)

    def test_modules_stay_below_hard_size_limit(self):
        oversized = []
        for path in production_files():
            lines = len(path.read_text(encoding="utf-8").splitlines())
            if lines > MAX_MODULE_LINES:
                oversized.append(f"{path.relative_to(PROJECT_ROOT)}:{lines}")
        self.assertEqual([], oversized)

    def test_production_files_have_no_merge_markers(self):
        affected = []
        for path in production_files():
            content = path.read_text(encoding="utf-8")
            if any(marker in content for marker in CONFLICT_MARKERS):
                affected.append(str(path.relative_to(PROJECT_ROOT)))
        self.assertEqual([], affected)

    def test_private_runtime_artifacts_are_gitignored(self):
        ignored = {
            line.strip()
            for line in (PROJECT_ROOT / ".gitignore").read_text(
                encoding="utf-8"
            ).splitlines()
        }

        self.assertIn(".env", ignored)
        self.assertIn("data/", ignored)

    def test_architecture_modules_keep_documented_paths(self):
        missing = []
        for module_path, documentation_path in ARCHITECTURE_MODULE_DOCS.items():
            documentation = (PROJECT_ROOT / documentation_path).read_text(
                encoding="utf-8"
            )
            if module_path.as_posix() not in documentation:
                missing.append(module_path.as_posix())
        self.assertEqual([], missing)

    @staticmethod
    def _tree(path: Path) -> ast.Module:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    @staticmethod
    def _is_public_api(node) -> bool:
        return (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and not node.name.startswith("_")
        )

    @staticmethod
    def _is_function(node) -> bool:
        """Erkennt synchrone und asynchrone Funktionen sowie Methoden."""
        return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))


if __name__ == "__main__":
    unittest.main()
