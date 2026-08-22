"""Safe boundary around the locally installed Vector SDK."""

import math
from collections.abc import Callable
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import anki_vector
from anki_vector.connection import ControlPriorityLevel
from anki_vector.messaging import protocol
from anki_vector.util import degrees

from vector.behavior_control import BehaviorControl, BehaviorControlError


MIN_VOLUME = 0
MAX_VOLUME = 100
MIN_HEAD_DEGREES = -22.0
MAX_HEAD_DEGREES = 45.0
MIN_LIFT_HEIGHT = 0.0
MAX_LIFT_HEIGHT = 1.0
MAX_ACTION_TIMEOUT = 30.0


class VectorSDKClient:
    """Connect to one Vector and expose failure-safe robot operations."""

    def __init__(
        self,
        serial: str,
        behavior_control: BehaviorControl | None = None,
    ):
        """Initialisiert die SDK-Grenze für einen Vector mit zentraler Verhaltenskontrolle."""
        self.serial = serial
        self.behavior_control = behavior_control or BehaviorControl()

    def test_connection(self) -> bool:
        """Prüft den SDK-Zugriff und meldet die aktuelle Batteriespannung."""
        print("Connecting directly to Vector SDK...")
        try:
            with self._robot() as robot:
                battery = robot.get_battery_state()
                self._report_connection(battery.battery_volts)
                return True
        except Exception as exc:
            return self._report_sdk_failure("Vector SDK connection", exc)

    def play_wav(self, path: str | Path, volume: int = 50) -> bool:
        """Überträgt eine validierte lokale WAV-Datei an Vectors Lautsprecher."""
        audio_path = Path(path)
        if not self._valid_audio_request(audio_path, volume):
            return False
        print(f"Sending audio to Vector: {audio_path.name}")
        try:
            with self.behavior_control.operation("speech"):
                with self._robot() as robot:
                    robot.audio.stream_wav_file(str(audio_path), volume=volume)
            print("Audio playback completed.")
            return True
        except Exception as exc:
            return self._report_sdk_failure("Audio playback", exc)

    def say(self, text: str) -> bool:
        """Nutzt Vectors native Sprachausgabe nur für nicht deutsche Rückfallfälle."""
        print(f"Sending speech to Vector: {text}")
        try:
            with self.behavior_control.operation("speech"):
                with self._robot() as robot:
                    robot.behavior.say_text(text)
            print("Speech command completed. [OK]")
            return True
        except Exception as exc:
            return self._report_sdk_failure("Speech command", exc)

    def set_head_angle(self, angle_degrees: float, timeout: float = 8.0) -> bool:
        """Bewegt den Kopf in einen validierten Winkel, ohne die Räder anzusteuern."""
        if not self._valid_range(
            angle_degrees,
            MIN_HEAD_DEGREES,
            MAX_HEAD_DEGREES,
        ):
            return self._report_invalid_action("Head angle is outside the safe range.")
        return self._run_action(
            "head movement",
            timeout,
            lambda robot: robot.behavior.set_head_angle(degrees(angle_degrees)),
        )

    def set_lift_height(self, height: float, timeout: float = 8.0) -> bool:
        """Bewegt den Lift auf eine sichere normierte Höhe ohne Radbewegung."""
        if not self._valid_range(height, MIN_LIFT_HEIGHT, MAX_LIFT_HEIGHT):
            return self._report_invalid_action("Lift height is outside the safe range.")
        return self._run_action(
            "lift movement",
            timeout,
            lambda robot: robot.behavior.set_lift_height(height),
        )

    def play_animation_trigger(self, trigger: str, timeout: float = 8.0) -> bool:
        """Spielt einen festen Auslöser einmalig und deaktiviert stets dessen Körperspur."""
        if not isinstance(trigger, str) or not trigger.strip():
            return self._report_invalid_action("Animation trigger must not be empty.")
        return self._run_action(
            "animation",
            timeout,
            lambda robot: robot.anim.play_animation_trigger(
                protocol.AnimationTrigger(name=trigger),
                loop_count=1,
                ignore_body_track=True,
            ),
        )

    def emergency_stop(self) -> bool:
        """Bricht SDK-Arbeit ab, stoppt alle Motoren und hält Verhalten verriegelt."""
        active = self.behavior_control.request_emergency_stop()
        print(f"Emergency stop requested for: {active or 'idle Vector'}")
        try:
            with self._robot() as robot:
                robot.motors.stop_all_motors()
            print("All Vector motors stopped. [OK]")
            return True
        except Exception as exc:
            return self._report_sdk_failure("Emergency motor stop", exc)

    def _run_action(
        self,
        label: str,
        timeout: float,
        operation: Callable[[object], Future],
    ) -> bool:
        """Führt eine SDK-Aktion unter Verhaltenskontrolle und fester Frist aus."""
        if not self._valid_action_timeout(timeout):
            return self._report_invalid_action("Action timeout is outside the safe range.")
        print(f"Starting Vector {label}...")
        try:
            with self.behavior_control.operation(label):
                self._execute_action(operation, timeout)
            print(f"Vector {label} completed. [OK]")
            return True
        except FutureTimeoutError:
            self.behavior_control.request_emergency_stop()
            print(f"Vector {label} timed out. Emergency stop is active. [ERROR]")
            return False
        except BehaviorControlError as exc:
            return self._report_sdk_failure(f"Vector {label} rejected", exc)
        except Exception as exc:
            return self._report_sdk_failure(f"Vector {label}", exc)

    def _execute_action(
        self,
        operation: Callable[[object], Future],
        timeout: float,
    ) -> None:
        """Verknüpft eine asynchrone SDK-Aktion mit Notstopp und Zeitüberschreitung."""
        with self._action_robot(timeout) as robot:
            future = operation(robot)
            self.behavior_control.attach_future(future)
            try:
                future.result(timeout=timeout)
            except FutureTimeoutError:
                future.cancel()
                self._stop_connected_robot(robot, timeout)
                raise
            finally:
                self.behavior_control.detach_future(future)

    @contextmanager
    def _action_robot(self, timeout: float) -> Iterator[object]:
        """Verbindet einen asynchronen Robot ausschließlich für eine begrenzte Aktion."""
        activation_timeout = max(1, math.ceil(timeout))
        robot = anki_vector.AsyncRobot(
            serial=self.serial,
            cache_animation_lists=False,
            behavior_activation_timeout=activation_timeout,
            behavior_control_level=ControlPriorityLevel.DEFAULT_PRIORITY,
        )
        robot.connect(timeout=activation_timeout)
        try:
            yield robot
        finally:
            robot.disconnect()

    @staticmethod
    def _stop_connected_robot(robot: object, timeout: float) -> None:
        """Versucht bei Zeitüberschreitung alle Motoren des verbundenen Robots zu stoppen."""
        try:
            stop_future = robot.motors.stop_all_motors()
            stop_future.result(timeout=min(timeout, 2.0))
        except Exception:
            pass

    def _robot(self):
        """Erzeugt einen synchronen SDK-Robot mit fester Kontrollpriorität."""
        return anki_vector.Robot(
            serial=self.serial,
            cache_animation_lists=False,
            behavior_control_level=ControlPriorityLevel.DEFAULT_PRIORITY,
        )

    @staticmethod
    def _valid_range(value: object, minimum: float, maximum: float) -> bool:
        """Prüft eine endliche Zahl gegen einen geschlossenen sicheren Bereich."""
        return (
            type(value) in (int, float)
            and math.isfinite(value)
            and minimum <= value <= maximum
        )

    @staticmethod
    def _valid_action_timeout(timeout: object) -> bool:
        """Prüft eine Aktionsfrist gegen die feste sichere Obergrenze."""
        return VectorSDKClient._valid_range(timeout, 0.1, MAX_ACTION_TIMEOUT)

    @staticmethod
    def _report_invalid_action(message: str) -> bool:
        """Meldet eine ungültige Aktion und liefert ein negatives Ergebnis."""
        print(message)
        return False

    @staticmethod
    def _valid_audio_request(audio_path: Path, volume: int) -> bool:
        """Prüft lokale Audiodatei und Lautstärke vor dem SDK-Zugriff."""
        if not audio_path.is_file():
            print(f"Audio file not found: {audio_path}")
            return False
        if not MIN_VOLUME <= volume <= MAX_VOLUME:
            print(f"Audio volume must be between {MIN_VOLUME} and {MAX_VOLUME}.")
            return False
        return True

    @staticmethod
    def _report_connection(battery_volts: float) -> None:
        """Meldet erfolgreiche Verbindung und gerundete Batteriespannung."""
        print("Vector SDK connection established. [OK]")
        print(f"Battery voltage: {battery_volts:.2f} V")

    @staticmethod
    def _report_sdk_failure(operation: str, error: Exception) -> bool:
        """Meldet heterogene SDK-Fehler an der gemeinsamen Hardwaregrenze."""
        # The third-party SDK exposes heterogeneous exception types at this boundary.
        print(f"{operation} failed. [ERROR]")
        print(f"Reason: {error}")
        return False
