"""Run one allowlisted physical Vector action for repeatable diagnostics."""

import argparse

from config.settings import settings
from vector.actions import SAFE_ACTION_NAMES, VectorActions
from vector.behavior_control import BehaviorControl
from vector.sdk_client import VectorSDKClient


EMERGENCY_STOP_COMMAND = "emergency_stop"


def main() -> int:
    """Execute exactly one named action and return a process status code."""
    parser = argparse.ArgumentParser(
        description="Run one controlled physical Vector action.",
    )
    parser.add_argument(
        "action",
        choices=(*SAFE_ACTION_NAMES, EMERGENCY_STOP_COMMAND),
    )
    selected = parser.parse_args().action
    control = BehaviorControl()
    client = VectorSDKClient(settings.VECTOR_SERIAL, control)
    actions = VectorActions(client, settings.ROBOT_ACTION_TIMEOUT)
    completed = (
        actions.emergency_stop()
        if selected == EMERGENCY_STOP_COMMAND
        else actions.perform(selected)
    )
    print(f"Physical action {selected}: {'PASS' if completed else 'FAIL'}")
    return 0 if completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
