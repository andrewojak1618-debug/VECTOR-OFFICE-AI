"""Expose bounded local metrics for the fixed Python quality rules."""

import ast
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tools.permissions import PermissionLevel
from tools.registry import ToolArguments, ToolDefinition, ToolOutput, ToolRegistry


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
MAX_FUNCTION_LINES = 35
MAX_MODULE_LINES = 399
MAX_QUALITY_COUNT = 100_000
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
SMALL_GERMAN_NUMBERS = (
    "null", "eins", "zwei", "drei", "vier", "fünf", "sechs", "sieben",
    "acht", "neun", "zehn", "elf", "zwölf", "dreizehn", "vierzehn",
    "fünfzehn", "sechzehn", "siebzehn", "achtzehn", "neunzehn",
)
GERMAN_TENS = {
    20: "zwanzig",
    30: "dreißig",
    40: "vierzig",
    50: "fünfzig",
    60: "sechzig",
    70: "siebzig",
    80: "achtzig",
    90: "neunzig",
}


@dataclass(frozen=True)
class CodeQualityStatus:
    """Hold content-free counters for the fixed Python quality inspection."""

    modules: int
    functions: int
    missing_module_docstrings: int
    missing_function_docstrings: int
    english_function_docstrings: int
    oversized_functions: int
    oversized_modules: int

    @property
    def issue_count(self) -> int:
        """Summiert alle erkannten Verstöße der festen Qualitätsregeln."""
        return sum((
            self.missing_module_docstrings,
            self.missing_function_docstrings,
            self.english_function_docstrings,
            self.oversized_functions,
            self.oversized_modules,
        ))


CodeQualityReader = Callable[[Path], CodeQualityStatus]


@dataclass(frozen=True)
class LocalCodeQualityStatusTool:
    """Return only bounded quality counters for the fixed project sources."""

    project_root: Path = PROJECT_ROOT
    status_reader: CodeQualityReader | None = None

    def __post_init__(self) -> None:
        """Setzt die feste lokale Qualitätsprüfung, wenn keine injiziert wurde."""
        if self.status_reader is None:
            object.__setattr__(self, "status_reader", inspect_code_quality)

    @property
    def definition(self) -> ToolDefinition:
        """Beschreibt das argumentlose lokale Codequalitätsstatus-Tool."""
        return ToolDefinition(
            name="development.code_quality_status",
            description="Return count-only health for fixed Python quality rules.",
            permission=PermissionLevel.READ_ONLY,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Liefert geprüfte Zähler und eine lokal erzeugte deutsche Zusammenfassung."""
        status = self.status_reader(self.project_root.resolve())
        _validate_status(status)
        return {
            "production_modules": status.modules,
            "production_functions": status.functions,
            "missing_module_docstrings": status.missing_module_docstrings,
            "missing_function_docstrings": status.missing_function_docstrings,
            "english_function_docstrings": status.english_function_docstrings,
            "oversized_functions": status.oversized_functions,
            "oversized_modules": status.oversized_modules,
            "issue_count": status.issue_count,
            "status": "clean" if status.issue_count == 0 else "issues",
            "spoken_text": _spoken_status(status),
        }


def register_code_quality_status_tool(
    registry: ToolRegistry,
    project_root: Path = PROJECT_ROOT,
    status_reader: CodeQualityReader | None = None,
) -> None:
    """Registriert die feste argumentlose lokale Qualitätsprüfung."""
    registry.register(LocalCodeQualityStatusTool(project_root, status_reader))


def production_files(project_root: Path = PROJECT_ROOT) -> tuple[Path, ...]:
    """Liefert ausschließlich Python-Dateien aus den festen Produktivpfaden."""
    root = project_root.resolve()
    main_module = root / "main.py"
    package_paths = tuple(root / name for name in PRODUCTION_PACKAGES)
    if not main_module.is_file() or not all(path.is_dir() for path in package_paths):
        raise OSError("Fixed production paths are incomplete.")
    files = [main_module.resolve()]
    for package_path in package_paths:
        files.extend(path.resolve() for path in package_path.rglob("*.py"))
    if not all(_is_within_root(path, root) for path in files):
        raise OSError("Production source escaped the fixed project root.")
    return tuple(sorted(files))


def inspect_code_quality(project_root: Path = PROJECT_ROOT) -> CodeQualityStatus:
    """Prüft feste Python-Quellen und verdichtet das Ergebnis auf Zähler."""
    results = tuple(_inspect_module(path) for path in production_files(project_root))
    return CodeQualityStatus(
        modules=sum(item.modules for item in results),
        functions=sum(item.functions for item in results),
        missing_module_docstrings=sum(item.missing_module_docstrings for item in results),
        missing_function_docstrings=sum(item.missing_function_docstrings for item in results),
        english_function_docstrings=sum(item.english_function_docstrings for item in results),
        oversized_functions=sum(item.oversized_functions for item in results),
        oversized_modules=sum(item.oversized_modules for item in results),
    )


def _inspect_module(path: Path) -> CodeQualityStatus:
    """Ermittelt inhaltsfreie Qualitätszähler für genau ein Python-Modul."""
    content = path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(path))
    functions = tuple(
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    return CodeQualityStatus(
        modules=1,
        functions=len(functions),
        missing_module_docstrings=int(ast.get_docstring(tree) is None),
        missing_function_docstrings=sum(ast.get_docstring(node) is None for node in functions),
        english_function_docstrings=sum(_uses_english_template(node) for node in functions),
        oversized_functions=sum(_function_lines(node) > MAX_FUNCTION_LINES for node in functions),
        oversized_modules=int(len(content.splitlines()) > MAX_MODULE_LINES),
    )


def _uses_english_template(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Erkennt die blockierten englischen Standardanfänge in Funktions-Docstrings."""
    return (ast.get_docstring(node) or "").startswith(ENGLISH_DOCSTRING_PREFIXES)


def _function_lines(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Berechnet die physische Zeilenzahl einer vollständig geparsten Funktion."""
    return node.end_lineno - node.lineno + 1


def _is_within_root(path: Path, root: Path) -> bool:
    """Prüft einen aufgelösten Quellpfad gegen die feste Projektwurzel."""
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _validate_status(status: CodeQualityStatus) -> None:
    """Validiert alle Qualitätszähler und ihre logischen Obergrenzen."""
    if not isinstance(status, CodeQualityStatus):
        raise TypeError("Code quality reader returned an invalid value.")
    counts = tuple(status.__dict__.values())
    if not all(type(value) is int and 0 <= value <= MAX_QUALITY_COUNT for value in counts):
        raise ValueError("Code quality counts must be bounded non-negative integers.")
    if status.modules < 1 or status.functions < 1:
        raise ValueError("Code quality inspection must include productive code.")
    if status.missing_module_docstrings > status.modules:
        raise ValueError("Module issue count exceeds inspected modules.")
    if any(value > status.functions for value in _function_issue_counts(status)):
        raise ValueError("Function issue count exceeds inspected functions.")


def _function_issue_counts(status: CodeQualityStatus) -> tuple[int, int, int]:
    """Liefert ausschließlich die drei funktionsbezogenen Qualitätszähler."""
    return (
        status.missing_function_docstrings,
        status.english_function_docstrings,
        status.oversized_functions,
    )


def _spoken_status(status: CodeQualityStatus) -> str:
    """Formuliert den Qualitätszustand ohne Pfade, Namen oder Quelltext."""
    if status.issue_count == 0:
        return (
            "Die lokale Codequalität erfüllt die festen Regeln. "
            f"Geprüft wurden {_spoken_number(status.modules)} Module. "
            f"Danach wurden {_spoken_number(status.functions)} Funktionen geprüft. "
            "Es gibt keine Verstöße gegen Docstrings oder Größenlimits."
        )
    return (
        "Die lokale Codequalität hat Regelverstöße. "
        f"{_issue_sentence(status.missing_module_docstrings, 'fehlende Modulbeschreibung', 'fehlende Modulbeschreibungen')} "
        f"{_issue_sentence(status.missing_function_docstrings, 'fehlende Funktionsbeschreibung', 'fehlende Funktionsbeschreibungen')} "
        f"{_issue_sentence(status.english_function_docstrings, 'englische Altformulierung', 'englische Altformulierungen')} "
        f"{_issue_sentence(status.oversized_functions, 'Funktionsüberschreitung', 'Funktionsüberschreitungen')} "
        f"{_issue_sentence(status.oversized_modules, 'Modulüberschreitung', 'Modulüberschreitungen')}"
    )


def _issue_sentence(value: int, singular: str, plural: str) -> str:
    """Formuliert einen Verstoßzähler als eigenen grammatikalischen Satz."""
    amount = "eine" if value == 1 else _spoken_number(value)
    noun = singular if value == 1 else plural
    verb = "wurde" if value == 1 else "wurden"
    return f"{amount.capitalize()} {noun} {verb} erkannt."


def _spoken_number(value: int) -> str:
    """Schreibt einen begrenzten nicht negativen Zähler als deutsches Zahlwort."""
    if value < 20:
        return SMALL_GERMAN_NUMBERS[value]
    if value < 100:
        remainder = value % 10
        tens = GERMAN_TENS[value - remainder]
        return tens if remainder == 0 else f"{_number_prefix(remainder)}und{tens}"
    if value < 1_000:
        remainder = value % 100
        hundreds = f"{_number_prefix(value // 100)}hundert"
        return hundreds if remainder == 0 else f"{hundreds}{_spoken_number(remainder)}"
    thousands = value // 1_000
    remainder = value % 1_000
    prefix = f"{_number_prefix(thousands)}tausend"
    return prefix if remainder == 0 else f"{prefix}{_spoken_number(remainder)}"


def _number_prefix(value: int) -> str:
    """Verwendet vor Hundert, Tausend und Und die gebundene Form von eins."""
    return "ein" if value == 1 else _spoken_number(value)
