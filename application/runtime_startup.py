"""Kapselt lokale Dienstprüfung und Vector-Verbindung des Anwendungsstarts."""

from collections.abc import Callable

from application.connection_supervisor import ConnectionSupervisor
from brain.ollama_runtime import OllamaRuntime
from diagnostics.events import DiagnosticLevel, StructuredDiagnosticReporter
from vector.behavior_control import BehaviorControl
from vector.client import VectorClient
from vector.sdk_client import VectorSDKClient


def ensure_ollama(settings, mode, diagnostics, connections) -> bool:
    """Stellt Ollama nur dann bereit, wenn der gewählte Modus es benötigt."""
    if not mode.needs_ollama:
        return True
    print("\nChecking local Ollama service...")
    runtime = OllamaRuntime(
        base_url=settings.OLLAMA_HOST,
        executable=settings.OLLAMA_EXECUTABLE,
    )
    ready = runtime.ensure_available()
    if ready and mode.local_voice_required:
        ready = runtime.preload_model(
            settings.OLLAMA_MODEL,
            settings.OLLAMA_REQUEST_TIMEOUT,
        )
    connections.observe("ollama", ready)
    if ready:
        diagnostics.emit(
            DiagnosticLevel.INFO,
            "ollama",
            "service.ready",
            local=True,
            status="available",
        )
        return True
    return _report_unavailable_ollama(mode, diagnostics)


def _report_unavailable_ollama(
    mode,
    diagnostics: StructuredDiagnosticReporter,
) -> bool:
    """Meldet den Ollama-Ausfall und liefert die erlaubte Startentscheidung."""
    allowed = _handle_unavailable_ollama(mode)
    diagnostics.emit(
        DiagnosticLevel.WARNING if allowed else DiagnosticLevel.ERROR,
        "ollama",
        "service.unavailable",
        local=True,
        status="fallback-allowed" if allowed else "required",
    )
    return allowed


def _handle_unavailable_ollama(mode) -> bool:
    """Entscheidet, ob ein Start ohne das nicht erreichbare Ollama zulässig ist."""
    if mode.provider == "ollama" or mode.local_voice_required:
        print("Ollama is required as the active LLM provider. [ERROR]")
        return False
    print("Continuing with OpenAI without local fallback.")
    return True


def connect_vector(
    settings,
    behavior_control: BehaviorControl | None = None,
    connections: ConnectionSupervisor | None = None,
) -> VectorSDKClient | None:
    """Prüft WirePod und baut anschließend die kontrollierte SDK-Verbindung auf."""
    print("\nChecking WirePod connection...")
    client = VectorClient(
        settings.WIREPOD_HOST,
        settings.WIREPOD_REQUEST_TIMEOUT,
    )
    ready = wait_for_connection(
        connections,
        "wirepod",
        client.check_wirepod,
    )
    if not ready:
        print("WirePod is not reachable. [ERROR]")
        return None
    print("WirePod is online. [OK]\n")
    print("Starting Vector SDK test...")
    vector = VectorSDKClient(settings.VECTOR_SERIAL, behavior_control)
    connected = wait_for_connection(
        connections,
        "vector-sdk",
        vector.test_connection,
    )
    return vector if connected else None


def wait_for_connection(
    connections: ConnectionSupervisor | None,
    service: str,
    health_check: Callable[[], bool],
) -> bool:
    """Führt eine direkte oder überwachte Verfügbarkeitsprüfung aus."""
    if connections is None:
        return health_check()
    return connections.wait_until_available(
        service,
        health_check,
        max_attempts=3,
    )
