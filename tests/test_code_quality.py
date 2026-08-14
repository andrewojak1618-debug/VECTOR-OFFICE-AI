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
    "vector",
    "voice",
)
# Fourteen lines remain the design target; 35 is the regression hard limit.
MAX_FUNCTION_LINES = 35
CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")


def production_files() -> tuple[Path, ...]:
    files = [PROJECT_ROOT / "main.py"]
    for package in PRODUCTION_PACKAGES:
        files.extend((PROJECT_ROOT / package).glob("*.py"))
    return tuple(files)


class CodeQualityTests(unittest.TestCase):
    """Prevent structural regressions that are cheap to detect statically."""

    def test_public_apis_have_docstrings(self):
        missing = []
        for path in production_files():
            for node in ast.walk(self._tree(path)):
                if self._is_public_api(node) and ast.get_docstring(node) is None:
                    missing.append(f"{path.name}:{node.lineno}:{node.name}")
        self.assertEqual([], missing)

    def test_functions_stay_below_hard_size_limit(self):
        oversized = []
        for path in production_files():
            for node in ast.walk(self._tree(path)):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    lines = node.end_lineno - node.lineno + 1
                    if lines > MAX_FUNCTION_LINES:
                        oversized.append(f"{path.name}:{node.name}:{lines}")
        self.assertEqual([], oversized)

    def test_production_files_have_no_merge_markers(self):
        affected = []
        for path in production_files():
            content = path.read_text(encoding="utf-8")
            if any(marker in content for marker in CONFLICT_MARKERS):
                affected.append(str(path.relative_to(PROJECT_ROOT)))
        self.assertEqual([], affected)

    @staticmethod
    def _tree(path: Path) -> ast.Module:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    @staticmethod
    def _is_public_api(node) -> bool:
        return (
            isinstance(node, (ast.FunctionDef, ast.ClassDef))
            and not node.name.startswith("_")
        )


if __name__ == "__main__":
    unittest.main()
