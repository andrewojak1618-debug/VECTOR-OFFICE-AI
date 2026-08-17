import unittest
from unittest.mock import MagicMock, call

from vector.actions import (
    DRIVE_ACTIONS_ENABLED,
    SAFE_ACTION_NAMES,
    VectorActions,
)


class VectorActionsTests(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client.set_head_angle.return_value = True
        self.client.set_lift_height.return_value = True
        self.client.play_animation_trigger.return_value = True
        self.actions = VectorActions(self.client, timeout=7)

    def test_allowlist_is_fixed_and_contains_no_drive_action(self):
        self.assertFalse(DRIVE_ACTIONS_ENABLED)
        self.assertEqual(
            (
                "head_up",
                "head_level",
                "lift_up",
                "lift_down",
                "greeting",
                "eyes_only",
                "reflective_expression",
            ),
            SAFE_ACTION_NAMES,
        )

    def test_head_actions_use_bounded_angles(self):
        self.assertTrue(self.actions.perform("head_up"))
        self.assertTrue(self.actions.perform("head_level"))

        self.client.set_head_angle.assert_any_call(25.0, 7.0)
        self.client.set_head_angle.assert_any_call(0.0, 7.0)

    def test_lift_actions_use_normalized_heights(self):
        self.assertTrue(self.actions.perform("lift_up"))
        self.assertTrue(self.actions.perform("lift_down"))

        self.client.set_lift_height.assert_any_call(0.7, 7.0)
        self.client.set_lift_height.assert_any_call(0.0, 7.0)

    def test_animation_aliases_use_only_reviewed_triggers(self):
        self.assertTrue(self.actions.perform("greeting"))
        self.assertTrue(self.actions.perform("eyes_only"))

        self.client.play_animation_trigger.assert_any_call(
            "ReactToGreeting",
            7.0,
        )
        self.client.play_animation_trigger.assert_any_call(
            "ObservingIdleEyesOnly",
            7.0,
        )

    def test_reflective_expression_combines_bounded_head_and_eyes(self):
        self.assertTrue(self.actions.perform("reflective_expression"))

        expected_timeout = 7.0
        self.client.assert_has_calls(
            (
                call.set_head_angle(18.0, expected_timeout),
                call.play_animation_trigger(
                    "ObservingIdleEyesOnly",
                    expected_timeout,
                ),
                call.set_head_angle(0.0, expected_timeout),
            )
        )

    def test_reflective_expression_resets_head_after_animation_failure(self):
        self.client.play_animation_trigger.return_value = False

        self.assertFalse(self.actions.perform("reflective_expression"))

        self.client.set_head_angle.assert_any_call(0.0, 7.0)

    def test_unknown_and_drive_actions_are_rejected(self):
        with self.assertRaises(ValueError):
            self.actions.perform("drive_forward")

        self.client.set_head_angle.assert_not_called()
        self.client.set_lift_height.assert_not_called()
        self.client.play_animation_trigger.assert_not_called()

    def test_emergency_stop_and_reset_delegate_to_central_control(self):
        self.client.emergency_stop.return_value = True

        self.assertTrue(self.actions.emergency_stop())
        self.actions.reset_emergency_stop()

        self.client.emergency_stop.assert_called_once_with()
        self.client.behavior_control.reset_emergency_stop.assert_called_once_with()

    def test_non_positive_timeout_is_rejected(self):
        with self.assertRaises(ValueError):
            VectorActions(self.client, timeout=0)


if __name__ == "__main__":
    unittest.main()
