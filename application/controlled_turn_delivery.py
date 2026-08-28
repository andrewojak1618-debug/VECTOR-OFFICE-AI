"""Liefert kontrollierte Tool- und Ausdrucksturns samt sicherer Zeitmessung aus."""

from application.contextual_tool_conversation import (
    ControlledContextualToolConversation,
)
from application.expression_conversation import ControlledExpressionConversation
from application.memory_conversation import ControlledMemoryConversation
from application.response_delivery import speak_answer
from application.tool_conversation import ControlledToolConversation
from diagnostics.response_latency import ResponseLatencyTrace
from vector.speech import VectorSpeech


def handle_tool_turn(
    controller: ControlledToolConversation | ControlledMemoryConversation | None,
    speech: VectorSpeech,
    user_text: str,
    trace: ResponseLatencyTrace,
) -> bool:
    """Verarbeitet einen kontrollierten Toolturn und misst seine Ausgabe."""
    if controller is None:
        return False
    result = controller.handle(user_text)
    if not result.handled:
        return False
    trace.prepared()
    if result.message:
        print(f"Vector: {result.message}")
    completed = _speak_result(speech, result.message, result.speak, trace)
    trace.finish(completed)
    return True


def handle_expression_turn(
    controller: ControlledExpressionConversation | None,
    speech: VectorSpeech,
    user_text: str,
    trace: ResponseLatencyTrace,
) -> bool:
    """Verarbeitet einen Ausdrucksturn und misst seine erreichbaren Grenzen."""
    if controller is None:
        return False
    result = controller.handle(user_text)
    if not result.handled:
        return False
    trace.prepared()
    if result.message:
        print(f"Vector: {result.message}")
    completed = _speak_result(speech, result.message, result.speak, trace)
    if result.delivery is not None:
        completed = result.delivery.speech_completed
        if not completed:
            print("Vector could not play the prepared response.")
    trace.finish(completed)
    return True


def handle_contextual_tool_turn(
    controller: ControlledContextualToolConversation | None,
    speech: VectorSpeech,
    user_text: str,
    trace: ResponseLatencyTrace,
) -> bool:
    """Verarbeitet einen geprüften Kontextvorschlag und misst seine Ausgabe."""
    if controller is None:
        return False
    result = controller.handle(user_text)
    if not result.handled:
        return False
    trace.prepared()
    if result.message:
        print(f"Vector: {result.message}")
    completed = _speak_result(speech, result.message, result.speak, trace)
    trace.finish(completed)
    return True


def _speak_result(
    speech: VectorSpeech,
    message: str,
    should_speak: bool,
    trace: ResponseLatencyTrace,
) -> bool:
    """Spricht einen vorhandenen Ergebnistext über die gemessene TTS-Grenze."""
    if not should_speak or not message:
        return True
    return speak_answer(speech, message, trace=trace)
