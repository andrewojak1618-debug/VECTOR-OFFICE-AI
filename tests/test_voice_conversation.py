import io
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from main import run_voice_conversation
from application.connection_supervisor import ConnectionSupervisor
from application.voice_recovery import CONNECTION_RECOVERY_NOTICE


class FakeAgent:
    def __init__(self):
        self.requests = []

    def respond(self, user_text):
        self.requests.append(user_text)
        return f"Antwort auf: {user_text}"


class FakeSpeech:
    def __init__(self):
        self.spoken = []

    def say(self, text):
        self.spoken.append(text)
        return True


class SequenceVoiceListener:
    def __init__(self, events=(), prime_failures=0):
        self.events = iter(events)
        self.prime_failures = prime_failures
        self.prime_count = 0
        self.wait_count = 0

    def prime(self):
        self.prime_count += 1
        if self.prime_count <= self.prime_failures:
            raise RuntimeError("private startup detail")

    def wait_for_transcript(self, _timeout):
        self.wait_count += 1
        event = next(self.events)
        if isinstance(event, BaseException):
            raise event
        return SimpleNamespace(text=event) if event is not None else None


class FakeExpressionConversation:
    def __init__(self):
        self.cancel_count = 0

    def cancel_pending(self):
        self.cancel_count += 1
        return True


class VoiceConversationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.agent = FakeAgent()
        self.speech = FakeSpeech()

    def test_normalized_exit_signal_ends_without_model_request(self):
        listener = SequenceVoiceListener(["  Vector   bitte beenden!  "])

        with patch("sys.stdout", new_callable=io.StringIO):
            run_voice_conversation(self.agent, self.speech, listener)

        self.assertEqual([], self.agent.requests)
        self.assertEqual([], self.speech.spoken)

    def test_spoken_abort_phrase_ends_session(self):
        listener = SequenceVoiceListener(["Gespräch abbrechen."])

        with patch("sys.stdout", new_callable=io.StringIO):
            run_voice_conversation(self.agent, self.speech, listener)

        self.assertEqual([], self.agent.requests)

    def test_observed_short_exit_variant_ends_session(self):
        listener = SequenceVoiceListener(["bitte beenden"])

        with patch("sys.stdout", new_callable=io.StringIO):
            run_voice_conversation(self.agent, self.speech, listener)

        self.assertEqual([], self.agent.requests)

    def test_transient_poll_failure_is_retried(self):
        listener = SequenceVoiceListener(
            [RuntimeError("private endpoint detail"), "hallo vector"],
        )

        with patch("application.conversation.time.sleep"), patch(
            "sys.stdout",
            new_callable=io.StringIO,
        ) as output:
            run_voice_conversation(
                self.agent,
                self.speech,
                listener,
                max_turns=1,
            )

        self.assertEqual(["hallo vector"], self.agent.requests)
        self.assertEqual(2, listener.wait_count)
        self.assertIn("temporarily unavailable", output.getvalue())
        self.assertNotIn("private endpoint detail", output.getvalue())

    def test_transient_poll_recovery_is_spoken_once_with_supervisor_delay(self):
        listener = SequenceVoiceListener(
            [RuntimeError("private endpoint detail"), "hallo vector"],
        )
        connections = ConnectionSupervisor()

        with patch("application.conversation.time.sleep") as sleep, patch(
            "sys.stdout",
            new_callable=io.StringIO,
        ):
            run_voice_conversation(
                self.agent,
                self.speech,
                listener,
                max_turns=1,
                connections=connections,
            )

        sleep.assert_called_once_with(1.0)
        self.assertEqual(
            [CONNECTION_RECOVERY_NOTICE, "Antwort auf: hallo vector"],
            self.speech.spoken,
        )
        self.assertFalse(connections.consume_recovery("wirepod"))

    def test_transient_prime_failure_is_retried(self):
        listener = SequenceVoiceListener(["hallo"], prime_failures=1)

        with patch("application.conversation.time.sleep"), patch(
            "sys.stdout",
            new_callable=io.StringIO,
        ):
            run_voice_conversation(
                self.agent,
                self.speech,
                listener,
                max_turns=1,
            )

        self.assertEqual(2, listener.prime_count)
        self.assertEqual(["hallo"], self.agent.requests)

    def test_transient_prime_recovery_is_spoken_before_first_answer(self):
        listener = SequenceVoiceListener(["hallo"], prime_failures=1)
        connections = ConnectionSupervisor()

        with patch("application.conversation.time.sleep"), patch(
            "sys.stdout",
            new_callable=io.StringIO,
        ):
            run_voice_conversation(
                self.agent,
                self.speech,
                listener,
                max_turns=1,
                connections=connections,
            )

        self.assertEqual(
            [CONNECTION_RECOVERY_NOTICE, "Antwort auf: hallo"],
            self.speech.spoken,
        )

    def test_five_consecutive_poll_failures_end_session(self):
        failures = [RuntimeError("private detail") for _ in range(5)]
        listener = SequenceVoiceListener(failures)

        with patch("application.conversation.time.sleep"), patch(
            "sys.stdout",
            new_callable=io.StringIO,
        ) as output:
            run_voice_conversation(self.agent, self.speech, listener)

        self.assertEqual(5, listener.wait_count)
        self.assertIn("failed repeatedly", output.getvalue())
        self.assertNotIn("private detail", output.getvalue())
        self.assertEqual([], self.agent.requests)

    def test_interrupt_during_prime_ends_without_traceback(self):
        listener = SequenceVoiceListener()
        listener.prime = Mock(side_effect=KeyboardInterrupt)

        with patch("sys.stdout", new_callable=io.StringIO) as output:
            run_voice_conversation(self.agent, self.speech, listener)

        self.assertIn("Conversation ended", output.getvalue())
        self.assertEqual([], self.agent.requests)

    def test_interrupt_during_response_ends_without_traceback(self):
        listener = SequenceVoiceListener(["hallo"])
        self.agent.respond = Mock(side_effect=KeyboardInterrupt)

        with patch("sys.stdout", new_callable=io.StringIO) as output:
            run_voice_conversation(self.agent, self.speech, listener)

        self.assertIn("Conversation ended", output.getvalue())
        self.assertEqual([], self.speech.spoken)

    def test_session_end_cancels_pending_expression_state(self):
        listener = SequenceVoiceListener(["vector beenden"])
        expression = FakeExpressionConversation()

        with patch(
            "application.conversation._create_expression_conversation",
            return_value=expression,
        ), patch("sys.stdout", new_callable=io.StringIO):
            run_voice_conversation(self.agent, self.speech, listener)

        self.assertEqual(1, expression.cancel_count)


if __name__ == "__main__":
    unittest.main()
