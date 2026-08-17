"""Provide bounded operating-system process controls for local supervision."""

import os
import subprocess
from pathlib import Path


class SingleInstanceLock:
    """Hold one non-blocking local file lock for a process lifetime."""

    def __init__(self, path: Path):
        self.path = path
        self._stream = None

    def acquire(self) -> bool:
        """Return whether this process acquired the single-instance lock."""
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
        """Release the held lock without deleting the harmless lock file."""
        if self._stream is None:
            return
        try:
            self._unlock_stream()
        finally:
            self._stream.close()
            self._stream = None

    def _prepare_stream(self) -> None:
        self._stream.seek(0, os.SEEK_END)
        if self._stream.tell() == 0:
            self._stream.write(b"0")
            self._stream.flush()
        self._stream.seek(0)

    def _lock_stream(self) -> None:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self._stream.fileno(), msvcrt.LK_NBLCK, 1)
            return
        import fcntl

        fcntl.flock(self._stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock_stream(self) -> None:
        self._stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self._stream.fileno(), msvcrt.LK_UNLCK, 1)
            return
        import fcntl

        fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)


def hidden_process_flags() -> int:
    """Return the platform flag for hidden local helper processes."""
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def process_exists(process_id: int) -> bool:
    """Check a process ID without sending a terminating signal."""
    if os.name == "nt":
        return _windows_process_exists(process_id)
    try:
        os.kill(process_id, 0)
    except OSError:
        return False
    return True


def stop_process_tree(process) -> None:
    """Stop only the supplied application process and its descendants."""
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
    """Return whether Windows currently exposes one chipper process."""
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chipper.exe", "/NH"],
            check=False,
            capture_output=True,
            text=True,
            creationflags=hidden_process_flags(),
        )
    except OSError:
        return False
    return "chipper.exe" in result.stdout.casefold()


def _windows_process_exists(process_id: int) -> bool:
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
