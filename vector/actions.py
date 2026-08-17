"""Allow only bounded, named Vector actions without wheel movement."""

from enum import Enum
from types import MappingProxyType

from vector.sdk_client import VectorSDKClient


DRIVE_ACTIONS_ENABLED = False
REFLECTIVE_HEAD_DEGREES = 18.0
REFLECTIVE_ANIMATION_TRIGGER = "ObservingIdleEyesOnly"


class SafeRobotAction(Enum):
    """Enumerate the complete action allowlist exposed to tools."""

    HEAD_UP = "head_up"
    HEAD_LEVEL = "head_level"
    LIFT_UP = "lift_up"
    LIFT_DOWN = "lift_down"
    GREETING = "greeting"
    EYES_ONLY = "eyes_only"
    REFLECTIVE_EXPRESSION = "reflective_expression"


SAFE_ACTION_NAMES = tuple(action.value for action in SafeRobotAction)
HEAD_ANGLES = MappingProxyType({
    SafeRobotAction.HEAD_UP: 25.0,
    SafeRobotAction.HEAD_LEVEL: 0.0,
})
LIFT_HEIGHTS = MappingProxyType({
    SafeRobotAction.LIFT_UP: 0.7,
    SafeRobotAction.LIFT_DOWN: 0.0,
})
ANIMATION_TRIGGERS = MappingProxyType({
    SafeRobotAction.GREETING: "ReactToGreeting",
    SafeRobotAction.EYES_ONLY: "ObservingIdleEyesOnly",
})


class VectorActions:
    """Map fixed safe action names onto bounded SDK client operations."""

    def __init__(self, client: VectorSDKClient, timeout: float = 8.0):
        if timeout <= 0:
            raise ValueError("Robot action timeout must be positive.")
        self.client = client
        self.timeout = float(timeout)

    def perform(self, action_name: str) -> bool:
        """Execute one allowlisted action and reject every other name."""
        action = self._parse_action(action_name)
        if action is SafeRobotAction.REFLECTIVE_EXPRESSION:
            return self._perform_reflective_expression()
        if action in HEAD_ANGLES:
            return self.client.set_head_angle(HEAD_ANGLES[action], self.timeout)
        if action in LIFT_HEIGHTS:
            return self.client.set_lift_height(LIFT_HEIGHTS[action], self.timeout)
        return self.client.play_animation_trigger(
            ANIMATION_TRIGGERS[action],
            self.timeout,
        )

    def _perform_reflective_expression(self) -> bool:
        if not self.client.set_head_angle(
            REFLECTIVE_HEAD_DEGREES,
            self.timeout,
        ):
            return False
        animated = self.client.play_animation_trigger(
            REFLECTIVE_ANIMATION_TRIGGER,
            self.timeout,
        )
        reset = self.client.set_head_angle(0.0, self.timeout)
        return animated and reset

    def emergency_stop(self) -> bool:
        """Cancel active behavior, stop all motors, and latch the stop state."""
        return self.client.emergency_stop()

    def reset_emergency_stop(self) -> None:
        """Explicitly re-enable actions after the physical situation is safe."""
        self.client.behavior_control.reset_emergency_stop()

    @staticmethod
    def available_actions() -> tuple[str, ...]:
        """Return the immutable public action allowlist."""
        return SAFE_ACTION_NAMES

    @staticmethod
    def _parse_action(action_name: str) -> SafeRobotAction:
        if not isinstance(action_name, str):
            raise TypeError("Robot action name must be text.")
        try:
            return SafeRobotAction(action_name.strip().casefold())
        except ValueError as exc:
            raise ValueError("Robot action is not allowlisted.") from exc
