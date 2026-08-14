import unittest
from concurrent.futures import Future

from vector.behavior_control import (
    BehaviorBusyError,
    BehaviorControl,
    EmergencyStopActiveError,
)


class BehaviorControlTests(unittest.TestCase):
    def test_operation_excludes_speech_and_actions(self):
        control = BehaviorControl()

        with control.operation("speech"):
            self.assertEqual("speech", control.active_operation)
            with self.assertRaises(BehaviorBusyError):
                with control.operation("head movement"):
                    pass

        self.assertIsNone(control.active_operation)

    def test_emergency_stop_cancels_future_and_blocks_new_work(self):
        control = BehaviorControl()
        future = Future()

        with control.operation("animation"):
            control.attach_future(future)
            self.assertEqual("animation", control.request_emergency_stop())

        self.assertTrue(future.cancelled())
        self.assertTrue(control.emergency_stop_active)
        with self.assertRaises(EmergencyStopActiveError):
            with control.operation("speech"):
                pass

    def test_explicit_reset_reenables_behavior(self):
        control = BehaviorControl()
        control.request_emergency_stop()

        control.reset_emergency_stop()

        with control.operation("head movement"):
            self.assertEqual("head movement", control.active_operation)

    def test_reset_is_rejected_while_an_operation_is_active(self):
        control = BehaviorControl()

        with control.operation("speech"):
            with self.assertRaises(BehaviorBusyError):
                control.reset_emergency_stop()


if __name__ == "__main__":
    unittest.main()
