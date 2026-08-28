"""Meldet die letzte bekannte Tool-Aktion ausschließlich mit sicheren Metadaten."""

from collections.abc import Callable
from dataclasses import dataclass
from types import MappingProxyType

from tools.audit_store import SQLiteToolAuditStore, ToolAuditRecord
from tools.permissions import PermissionLevel
from tools.registry import ToolArguments, ToolDefinition, ToolOutput, ToolRegistry
from tools.registry_types import ToolResultStatus


TOOL_NAME = "development.latest_tool_status"
LATEST_EVENT_SCAN_LIMIT = 50
ACTION_LABELS = MappingProxyType({
    "development.code_quality_status": "Codequalität prüfen",
    "development.documentation_status": "Dokumentationsstatus prüfen",
    "development.latest_change": "letzte Projektänderung prüfen",
    "development.next_roadmap_item": "nächsten Projektpunkt prüfen",
    "development.open_project_directory": "Dokumentationsordner öffnen",
    "development.open_project_document": "Projektdokument öffnen",
    "development.project_document_catalog": "Projektdokumente auflisten",
    "development.summarize_project_document": "Projektdokument zusammenfassen",
    "development.project_status": "Projektstatus prüfen",
    "development.run_core_tests": "Projekttests ausführen",
    "knowledge.library_status": "Bibliotheksstatus prüfen",
    "memory.local_status": "Gedächtnisstatus prüfen",
    "office.local_datetime": "Datum und Uhrzeit prüfen",
    "research.python_latest_version": "Python-Version prüfen",
    "research.python_source_status": "Python-Quelle prüfen",
    "system.local_service_status": "lokale Dienste prüfen",
    "vector.emergency_stop": "Notfallstopp ausführen",
    "vector.list_actions": "Robot-Aktionen auflisten",
    "vector.perform_action": "Robot-Aktion ausführen",
})
STATUS_SENTENCES = MappingProxyType({
    ToolResultStatus.SUCCESS: "Sie wurde erfolgreich abgeschlossen.",
    ToolResultStatus.BLOCKED: "Sie wurde sicher blockiert.",
    ToolResultStatus.INVALID: "Sie war ungültig und wurde nicht ausgeführt.",
    ToolResultStatus.FAILED: "Sie war nicht erfolgreich.",
})

LatestToolStatusReader = Callable[[], ToolAuditRecord | None]


@dataclass(frozen=True)
class LatestToolStatusTool:
    """Formuliert einen geprüften Auditstatus ohne Argumente oder Fehlerdetails."""

    reader: LatestToolStatusReader

    @property
    def definition(self) -> ToolDefinition:
        """Beschreibt die argumentlose und rein lesende Auditstatus-Abfrage."""
        return ToolDefinition(
            name=TOOL_NAME,
            description="Return the last approved tool status without private data.",
            permission=PermissionLevel.READ_ONLY,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Liefert ausschließlich eine feste Bezeichnung und einen sicheren Status."""
        record = self.reader()
        if record is None:
            return {
                "found": False,
                "action": "",
                "status": "",
                "spoken_text": "Es ist keine kontrollierte Aktion verfügbar.",
            }
        label = _validated_label(record)
        return {
            "found": True,
            "action": label,
            "status": record.status.value,
            "spoken_text": _spoken_status(label, record.status),
        }


def register_latest_tool_status_tool(
    registry: ToolRegistry,
    reader: LatestToolStatusReader,
) -> None:
    """Registriert die inhaltsfreie Abfrage des letzten Toolstatus."""
    if not callable(reader):
        raise TypeError("Latest tool status reader must be callable.")
    registry.register(LatestToolStatusTool(reader))


def create_latest_tool_status_reader(
    store: SQLiteToolAuditStore,
) -> LatestToolStatusReader:
    """Erzeugt einen Leser, der unbekannte und eigene Ereignisse überspringt."""
    if not isinstance(store, SQLiteToolAuditStore):
        raise TypeError("Latest tool status requires a SQLiteToolAuditStore.")

    def read() -> ToolAuditRecord | None:
        """Wählt das jüngste bekannte Ereignis ohne die Statusabfrage selbst."""
        for record in store.list_events(LATEST_EVENT_SCAN_LIMIT):
            if record.tool_name in ACTION_LABELS:
                return record
        return None

    return read


def _validated_label(record: ToolAuditRecord) -> str:
    """Validiert Audittyp, Toolname und Status gegen feste lokale Werte."""
    if not isinstance(record, ToolAuditRecord):
        raise TypeError("Latest tool status reader returned an invalid value.")
    label = ACTION_LABELS.get(record.tool_name)
    if label is None or record.status not in STATUS_SENTENCES:
        raise ValueError("Latest tool status record is not allowlisted.")
    return label


def _spoken_status(label: str, status: ToolResultStatus) -> str:
    """Formuliert den geprüften Status ohne Zeit-, Argument- oder Fehlerdaten."""
    return f"Die letzte kontrollierte Aktion war: {label}. {STATUS_SENTENCES[status]}"
