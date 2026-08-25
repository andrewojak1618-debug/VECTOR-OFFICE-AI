"""Provide bounded operating-system process controls for local supervision."""

import os
import csv
import subprocess
from io import StringIO
from pathlib import Path


class SingleInstanceLock:
    """Hold one non-blocking local file lock for a process lifetime."""

    def __init__(self, path: Path):
        """Initialisiert eine prozessweite Sperre an einem festen lokalen Pfad."""
        self.path = path
        self._stream = None

    def acquire(self) -> bool:
        """Meldet, ob dieser Prozess die Einzelinstanzsperre erhalten hat."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self.path.open("a+b")
        self._prepare_stream()
        try:
            self._lock_stream()
        except OSError:
            self._stream.close()
            self._stream = None
            return False
        return True

    def release(self) -> None:
        """Gibt die Sperre frei, ohne die harmlose Sperrdatei zu löschen."""
        if self._stream is None:
            return
        try:
            self._unlock_stream()
        finally:
            self._stream.close()
            self._stream = None

    def _prepare_stream(self) -> None:
        """Bereitet genau ein sperrbares Byte in der lokalen Datei vor."""
        self._stream.seek(0, os.SEEK_END)
        if self._stream.tell() == 0:
            self._stream.write(b"0")
            self._stream.flush()
        self._stream.seek(0)

    def _lock_stream(self) -> None:
        """Sperrt die Datei plattformspezifisch und ohne zu warten."""
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self._stream.fileno(), msvcrt.LK_NBLCK, 1)
            return
        import fcntl

        fcntl.flock(self._stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock_stream(self) -> None:
        """Löst die gehaltene Dateisperre plattformspezifisch."""
        self._stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self._stream.fileno(), msvcrt.LK_UNLCK, 1)
            return
        import fcntl

        fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)


def hidden_process_flags() -> int:
    """Liefert das Plattformflag für unsichtbare lokale Hilfsprozesse."""
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def process_exists(process_id: int) -> bool:
    """Prüft eine Prozess-ID, ohne ein beendendes Signal zu senden."""
    if os.name == "nt":
        return _windows_process_exists(process_id)
    try:
        os.kill(process_id, 0)
    except OSError:
        return False
    return True


def stop_process_tree(process) -> None:
    """Beendet nur den angegebenen Anwendungsprozess samt Nachkommen."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=hidden_process_flags(),
        )
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def wirepod_process_running() -> bool:
    """Prüft unter Windows, ob aktuell ein Chipper-Prozess sichtbar ist."""
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chipper.exe", "/NH"],
            check=False,
            capture_output=True,
            creationflags=hidden_process_flags(),
        )
    except OSError:
        return False
    output = result.stdout or b""
    return b"chipper.exe" in output.lower()


def wirepod_process_started_at() -> float | None:
    """Liefert die älteste lokale Chipper-Startzeit als Unix-Zeitstempel."""
    if os.name != "nt":
        return None
    start_times = [
        started
        for process_id in _wirepod_process_ids()
        if (started := _windows_process_started_at(process_id)) is not None
    ]
    return min(start_times) if start_times else None


def stop_wirepod_processes() -> bool:
    """Beendet ausschließlich lokale Chipper-Prozesse samt Nachkommen."""
    if os.name != "nt" or not wirepod_process_running():
        return True
    try:
        result = subprocess.run(
            ["taskkill", "/IM", "chipper.exe", "/T", "/F"],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=hidden_process_flags(),
        )
    except OSError:
        return False
    return result.returncode == 0


def _wirepod_process_ids() -> tuple[int, ...]:
    """Liest ausschließlich Prozess-IDs exakter Chipper-Prozesse aus."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chipper.exe", "/FO", "CSV", "/NH"],
            check=False,
            capture_output=True,
            creationflags=hidden_process_flags(),
        )
    except OSError:
        return ()
    text = (result.stdout or b"").decode("utf-8", errors="ignore")
    rows = csv.reader(StringIO(text))
    return tuple(
        int(row[1])
        for row in rows
        if len(row) >= 2 and row[0].casefold() == "chipper.exe" and row[1].isdigit()
    )


def _windows_process_started_at(process_id: int) -> float | None:
    """Ermittelt eine Windows-Prozessstartzeit mit minimalem Lesezugriff."""
    import ctypes
    from ctypes import wintypes

    kernel32 = _process_time_api(ctypes, wintypes)
    handle = kernel32.OpenProcess(0x1000, False, process_id)
    if not handle:
        return None
    creation = wintypes.FILETIME()
    exit_time = wintypes.FILETIME()
    kernel_time = wintypes.FILETIME()
    user_time = wintypes.FILETIME()
    try:
        success = kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        )
    finally:
        kernel32.CloseHandle(handle)
    if not success:
        return None
    ticks = creation.dwLowDateTime + (creation.dwHighDateTime << 32)
    return (ticks - 116_444_736_000_000_000) / 10_000_000


def _process_time_api(ctypes, wintypes):
    """Konfiguriert die sicheren Windows-Signaturen für Prozesszeiten."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    file_time_pointer = ctypes.POINTER(wintypes.FILETIME)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = (
        wintypes.HANDLE,
        file_time_pointer,
        file_time_pointer,
        file_time_pointer,
        file_time_pointer,
    )
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


def _windows_process_exists(process_id: int) -> bool:
    """Prüft eine Windows-Prozess-ID über eine minimale Handle-Berechtigung."""
    import ctypes
    from ctypes import wintypes

    query_limited_information = 0x1000
    access_denied = 5
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(query_limited_information, False, process_id)
    if not handle:
        return ctypes.get_last_error() == access_denied
    exit_code = wintypes.DWORD()
    queried = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
    kernel32.CloseHandle(handle)
    return bool(queried) and exit_code.value == still_active
