"""Safe boundary around the locally installed Vector SDK."""

from pathlib import Path

import anki_vector


MIN_VOLUME = 0
MAX_VOLUME = 100


class VectorSDKClient:
    """Connect to one Vector and expose failure-safe robot operations."""

    def __init__(self, serial: str):
        self.serial = serial

    def test_connection(self) -> bool:
        """Verify SDK access and report the current battery voltage."""
        print("Connecting directly to Vector SDK...")
        try:
            with self._robot() as robot:
                battery = robot.get_battery_state()
                self._report_connection(battery.battery_volts)
                return True
        except Exception as exc:
            return self._report_sdk_failure("Vector SDK connection", exc)

    def play_wav(self, path: str | Path, volume: int = 50) -> bool:
        """Stream one validated local WAV file through Vector's speaker."""
        audio_path = Path(path)
        if not self._valid_audio_request(audio_path, volume):
            return False
        print(f"Sending audio to Vector: {audio_path.name}")
        try:
            with self._robot() as robot:
                robot.audio.stream_wav_file(str(audio_path), volume=volume)
            print("Audio playback completed.")
            return True
        except Exception as exc:
            return self._report_sdk_failure("Audio playback", exc)

    def say(self, text: str) -> bool:
        """Use Vector's native speech command for non-German fallback cases."""
        print(f"Sending speech to Vector: {text}")
        try:
            with self._robot() as robot:
                robot.behavior.say_text(text)
            print("Speech command completed. [OK]")
            return True
        except Exception as exc:
            return self._report_sdk_failure("Speech command", exc)

    def _robot(self):
        return anki_vector.Robot(
            serial=self.serial,
            cache_animation_lists=False,
        )

    @staticmethod
    def _valid_audio_request(audio_path: Path, volume: int) -> bool:
        if not audio_path.is_file():
            print(f"Audio file not found: {audio_path}")
            return False
        if not MIN_VOLUME <= volume <= MAX_VOLUME:
            print(f"Audio volume must be between {MIN_VOLUME} and {MAX_VOLUME}.")
            return False
        return True

    @staticmethod
    def _report_connection(battery_volts: float) -> None:
        print("Vector SDK connection established. [OK]")
        print(f"Battery voltage: {battery_volts:.2f} V")

    @staticmethod
    def _report_sdk_failure(operation: str, error: Exception) -> bool:
        # The third-party SDK exposes heterogeneous exception types at this boundary.
        print(f"{operation} failed. [ERROR]")
        print(f"Reason: {error}")
        return False
