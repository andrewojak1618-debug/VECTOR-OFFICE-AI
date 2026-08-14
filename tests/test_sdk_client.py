import tempfile
import unittest
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
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

    def test_head_action_uses_async_sdk_and_safe_default_priority(self):
        robot, future = self._async_robot()
        robot.behavior.set_head_angle.return_value = future

        with patch("vector.sdk_client.anki_vector.AsyncRobot", return_value=robot):
            result = VectorSDKClient("test-serial").set_head_angle(25, timeout=4)

        self.assertTrue(result)
        self.assertEqual(25, robot.behavior.set_head_angle.call_args.args[0].degrees)
        future.result.assert_called_once_with(timeout=4)
        robot.connect.assert_called_once_with(timeout=4)
        robot.disconnect.assert_called_once_with()

    def test_lift_action_uses_normalized_height(self):
        robot, future = self._async_robot()
        robot.behavior.set_lift_height.return_value = future

        with patch("vector.sdk_client.anki_vector.AsyncRobot", return_value=robot):
            result = VectorSDKClient("test-serial").set_lift_height(0.7)

        self.assertTrue(result)
        robot.behavior.set_lift_height.assert_called_once_with(0.7)

    def test_animation_runs_once_with_body_track_disabled(self):
        robot, future = self._async_robot()
        robot.anim.play_animation_trigger.return_value = future

        with patch("vector.sdk_client.anki_vector.AsyncRobot", return_value=robot):
            result = VectorSDKClient("test-serial").play_animation_trigger(
                "ReactToGreeting"
            )

        self.assertTrue(result)
        call = robot.anim.play_animation_trigger.call_args
        self.assertEqual("ReactToGreeting", call.args[0].name)
        self.assertEqual(1, call.kwargs["loop_count"])
        self.assertTrue(call.kwargs["ignore_body_track"])

    def test_action_timeout_cancels_work_stops_motors_and_latches_stop(self):
        robot, future = self._async_robot()
        future.result.side_effect = FutureTimeoutError
        robot.behavior.set_head_angle.return_value = future

        with patch("vector.sdk_client.anki_vector.AsyncRobot", return_value=robot):
            client = VectorSDKClient("test-serial")
            result = client.set_head_angle(25, timeout=1)

        self.assertFalse(result)
        future.cancel.assert_called_once_with()
        robot.motors.stop_all_motors.assert_called_once_with()
        self.assertTrue(client.behavior_control.emergency_stop_active)

    def test_busy_behavior_control_rejects_simultaneous_speech(self):
        client = VectorSDKClient("test-serial")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "speech.wav"
            path.touch()
            with client.behavior_control.operation("head movement"):
                with patch("vector.sdk_client.anki_vector.Robot") as factory:
                    self.assertFalse(client.play_wav(path))

        factory.assert_not_called()

    def test_emergency_stop_cancels_behavior_and_stops_all_motors(self):
        robot_context, robot = self._robot_context()
        with patch("vector.sdk_client.anki_vector.Robot", return_value=robot_context):
            client = VectorSDKClient("test-serial")
            result = client.emergency_stop()

        self.assertTrue(result)
        self.assertTrue(client.behavior_control.emergency_stop_active)
        robot.motors.stop_all_motors.assert_called_once_with()

    def test_invalid_action_values_never_connect(self):
        with patch("vector.sdk_client.anki_vector.AsyncRobot") as factory:
            client = VectorSDKClient("test-serial")
            self.assertFalse(client.set_head_angle(90))
            self.assertFalse(client.set_lift_height(-0.1))
            self.assertFalse(client.play_animation_trigger(""))

        factory.assert_not_called()

    @staticmethod
    def _robot_context():
        context = MagicMock()
        robot = context.__enter__.return_value
        return context, robot

    @staticmethod
    def _async_robot():
        robot = MagicMock()
        future = MagicMock(spec=Future)
        stop_future = MagicMock(spec=Future)
        robot.motors.stop_all_motors.return_value = stop_future
        return robot, future


if __name__ == "__main__":
    unittest.main()
