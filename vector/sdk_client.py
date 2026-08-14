from pathlib import Path

import anki_vector


class VectorSDKClient:
    def __init__(self, serial: str):
        self.serial = serial

    def test_connection(self) -> bool:
        print("Connecting directly to Vector SDK...")

        try:
            with anki_vector.Robot(
                serial=self.serial,
                cache_animation_lists=False,
            ) as robot:
                battery = robot.get_battery_state()

                print("Vector SDK connection established. [OK]")
                print(f"Battery voltage: {battery.battery_volts:.2f} V")

                return True

        except Exception as exc:
            print("Vector SDK connection failed. [ERROR]")
            print(f"Reason: {exc}")
            return False

    def play_wav(self, path: str | Path, volume: int = 50) -> bool:
        audio_path = Path(path)

        if not audio_path.is_file():
            print(f"Audio file not found: {audio_path}")
            return False

        if not 0 <= volume <= 100:
            print("Audio volume must be between 0 and 100.")
            return False

        print(f"Sending audio to Vector: {audio_path.name}")

        try:
            with anki_vector.Robot(
                serial=self.serial,
                cache_animation_lists=False,
            ) as robot:
                robot.audio.stream_wav_file(
                    str(audio_path),
                    volume=volume,
                )

                print("Audio playback completed.")
                return True

        except Exception as exc:
            print("Audio playback failed.")
            print(f"Reason: {exc}")
            return False

    def say(self, text: str) -> bool:
        print(f"Sending speech to Vector: {text}")

        try:
            with anki_vector.Robot(
                serial=self.serial,
                cache_animation_lists=False,
            ) as robot:
                robot.behavior.say_text(text)

                print("Speech command completed. [OK]")
                return True

        except Exception as exc:
            print("Speech command failed. [ERROR]")
            print(f"Reason: {exc}")
            return False
