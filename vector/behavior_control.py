"""Coordinate exclusive robot behavior and a latched emergency stop."""

from concurrent.futures import Future
from contextlib import contextmanager
from threading import Event, Lock
from typing import Iterator


class BehaviorControlError(RuntimeError):
    """Describe a rejected request at the shared behavior boundary."""


class BehaviorBusyError(BehaviorControlError):
    """Report that speech or another action already owns the robot."""


class EmergencyStopActiveError(BehaviorControlError):
    """Report that behavior remains blocked after an emergency stop."""


class BehaviorControl:
    """Serialize speech and actions and centrally cancel active SDK work."""

    def __init__(self):
        self._operation_lock = Lock()
        self._state_lock = Lock()
        self._emergency_stop = Event()
        self._active_operation: str | None = None
        self._active_future: Future | None = None

    @contextmanager
    def operation(self, name: str) -> Iterator[None]:
        """Claim exclusive behavior control without waiting behind other work."""
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Behavior operation name must not be empty.")
        self._require_ready()
        if not self._operation_lock.acquire(blocking=False):
            active = self.active_operation or "another operation"
            raise BehaviorBusyError(f"Vector is busy with {active}.")
        try:
            self._require_ready()
            with self._state_lock:
                self._active_operation = normalized_name
            yield
        finally:
            with self._state_lock:
                self._active_future = None
                self._active_operation = None
            self._operation_lock.release()

    def attach_future(self, future: Future) -> None:
        """Attach one cancellable SDK future to the active operation."""
        if not isinstance(future, Future):
            raise TypeError("Active SDK work must be a Future.")
        with self._state_lock:
            if self._active_operation is None:
                raise RuntimeError("No behavior operation is active.")
            self._active_future = future
            should_cancel = self._emergency_stop.is_set()
        if should_cancel:
            future.cancel()
            raise EmergencyStopActiveError("Vector emergency stop is active.")

    def detach_future(self, future: Future) -> None:
        """Forget a completed SDK future without affecting newer work."""
        with self._state_lock:
            if self._active_future is future:
                self._active_future = None

    def request_emergency_stop(self) -> str | None:
        """Latch the stop state and cancel the currently attached SDK future."""
        self._emergency_stop.set()
        with self._state_lock:
            active_operation = self._active_operation
            future = self._active_future
        if future is not None:
            future.cancel()
        return active_operation

    def reset_emergency_stop(self) -> None:
        """Re-enable behavior only when no operation currently owns control."""
        if self._operation_lock.locked():
            raise BehaviorBusyError("Cannot reset while Vector is busy.")
        self._emergency_stop.clear()

    @property
    def emergency_stop_active(self) -> bool:
        """Report whether the latched emergency stop blocks new behavior."""
        return self._emergency_stop.is_set()

    @property
    def active_operation(self) -> str | None:
        """Return the current non-sensitive operation label, if any."""
        with self._state_lock:
            return self._active_operation

    def _require_ready(self) -> None:
        if self._emergency_stop.is_set():
            raise EmergencyStopActiveError("Vector emergency stop is active.")
