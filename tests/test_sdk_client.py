import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from vector.sdk_client import VectorSDKClient


class VectorSDKClientTests(unittest.TestCase):
    def test_connection_reports_successful_robot_access(self):
        robot_context, robot = self._robot_context()
        robot.get_battery_state.return_value = SimpleNamespace(
            battery_volts=4.15
        )

        with patch("vector.sdk_client.anki_vector.Robot", return_value=robot_context):
            self.assertTrue(VectorSDKClient("test-serial").test_connection())

        robot.get_battery_state.assert_called_once_with()

    def test_play_wav_streams_file_with_requested_volume(self):
        robot_context, robot = self._robot_context()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "speech.wav"
            path.touch()
            with patch(
                "vector.sdk_client.anki_vector.Robot",
                return_value=robot_context,
            ):
                result = VectorSDKClient("test-serial").play_wav(path, volume=90)

        self.assertTrue(result)
        robot.audio.stream_wav_file.assert_called_once_with(str(path), volume=90)

    def test_play_wav_rejects_invalid_volume_before_sdk_access(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "speech.wav"
            path.touch()
            with patch("vector.sdk_client.anki_vector.Robot") as robot_factory:
                result = VectorSDKClient("test-serial").play_wav(path, volume=101)

        self.assertFalse(result)
        robot_factory.assert_not_called()

    def test_native_speech_uses_robot_behavior(self):
        robot_context, robot = self._robot_context()
        with patch("vector.sdk_client.anki_vector.Robot", return_value=robot_context):
            result = VectorSDKClient("test-serial").say("Hallo")

        self.assertTrue(result)
        robot.behavior.say_text.assert_called_once_with("Hallo")

    @staticmethod
    def _robot_context():
        context = MagicMock()
        robot = context.__enter__.return_value
        return context, robot


if __name__ == "__main__":
    unittest.main()
