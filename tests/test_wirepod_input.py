import unittest

import httpx

from voice.wirepod_input import (
    WirePodTranscriptListener,
    WirePodTranscriptTimeoutError,
)


LOG_LINE = (
    "2026.08.14 15:30:00: Intent matched: intent_knowledge_promptquestion, "
    "transcribed text: 'wie geht es dir vector', device: 0dd1fd3b"
)
NO_AUDIO_LINE = (
    "2026.08.14 15:29:59: Intent matched: intent_system_noaudio, "
    "transcribed text: '', device: 0dd1fd3b"
)


def _log_line(timestamp, text="wie geht es dir vector", device="0dd1fd3b"):
    return (
        f"{timestamp}: Intent matched: intent_knowledge_promptquestion, "
        f"transcribed text: '{text}', device: {device}"
    )


class WirePodTranscriptListenerTests(unittest.TestCase):
    def test_parse_logs_extracts_transcript_metadata(self):
        events = WirePodTranscriptListener.parse_logs(
            f"unrelated line\n{LOG_LINE}\n"
        )

        self.assertEqual(1, len(events))
        self.assertEqual("wie geht es dir vector", events[0].text)
        self.assertEqual("0dd1fd3b", events[0].device)
        self.assertEqual(
            "intent_knowledge_promptquestion",
            events[0].intent,
        )

    def test_parse_logs_ignores_semantically_invalid_timestamp(self):
        invalid = _log_line("2026.99.14 15:30:00")

        self.assertEqual((), WirePodTranscriptListener.parse_logs(invalid))

    def test_poll_returns_only_new_transcripts(self):
        responses = iter(("", LOG_LINE, LOG_LINE))

        def handle_request(request):
            return httpx.Response(200, text=next(responses))

        client = httpx.Client(
            base_url="http://test",
            transport=httpx.MockTransport(handle_request),
        )
        listener = WirePodTranscriptListener(
            "http://test",
            client=client,
        )

        listener.prime()

        self.assertEqual("wie geht es dir vector", listener.poll()[0].text)
        self.assertEqual((), listener.poll())

    def test_endpoint_errors_are_sanitized(self):
        def handle_request(request):
            raise httpx.ConnectError("sensitive transport details")

        client = httpx.Client(
            base_url="http://test",
            transport=httpx.MockTransport(handle_request),
        )
        listener = WirePodTranscriptListener(
            "http://test",
            client=client,
        )

        with self.assertRaisesRegex(RuntimeError, "endpoint is unavailable"):
            listener.poll()

    def test_endpoint_timeout_is_reported_separately(self):
        def handle_request(request):
            raise httpx.ReadTimeout("private details", request=request)

        client = httpx.Client(
            base_url="http://test",
            transport=httpx.MockTransport(handle_request),
        )
        listener = WirePodTranscriptListener("http://test", client=client)

        with self.assertRaisesRegex(WirePodTranscriptTimeoutError, "timed out"):
            listener.poll()

    def test_request_timeout_is_bounded(self):
        for timeout in (0.9, 30.1):
            with self.subTest(timeout=timeout), self.assertRaisesRegex(
                ValueError,
                "timeout",
            ):
                WirePodTranscriptListener(
                    "http://test",
                    request_timeout=timeout,
                )

    def test_wait_ignores_no_audio_event(self):
        responses = iter(("", NO_AUDIO_LINE, f"{NO_AUDIO_LINE}\n{LOG_LINE}"))

        def handle_request(request):
            return httpx.Response(200, text=next(responses))

        client = httpx.Client(
            base_url="http://test",
            transport=httpx.MockTransport(handle_request),
        )
        listener = WirePodTranscriptListener(
            "http://test",
            poll_interval=0.001,
            client=client,
        )

        event = listener.wait_for_transcript(timeout=0.1)

        self.assertIsNotNone(event)
        self.assertEqual("wie geht es dir vector", event.text)

    def test_wait_suppresses_same_transcript_with_new_timestamp(self):
        duplicate = _log_line("2026.08.14 15:30:02", "WIE GEHT ES DIR VECTOR?")
        next_question = _log_line("2026.08.14 15:30:03", "wie spät ist es")
        responses = iter(("", LOG_LINE, duplicate, next_question))
        listener = self._listener_for_responses(responses)

        first = listener.wait_for_transcript(timeout=0.1)
        second = listener.wait_for_transcript(timeout=0.1)

        self.assertEqual("wie geht es dir vector", first.text)
        self.assertEqual("wie spät ist es", second.text)

    def test_same_transcript_after_window_is_accepted(self):
        later = _log_line("2026.08.14 15:30:04")
        responses = iter(("", LOG_LINE, later))
        listener = self._listener_for_responses(responses)

        first = listener.wait_for_transcript(timeout=0.1)
        second = listener.wait_for_transcript(timeout=0.1)

        self.assertEqual(first.text, second.text)

    def test_same_transcript_from_other_device_is_not_suppressed(self):
        other_device = _log_line(
            "2026.08.14 15:30:01",
            device="another-vector",
        )
        responses = iter(("", LOG_LINE, other_device))
        listener = self._listener_for_responses(responses)

        listener.wait_for_transcript(timeout=0.1)
        event = listener.wait_for_transcript(timeout=0.1)

        self.assertEqual("another-vector", event.device)

    def test_duplicate_history_contains_only_fingerprints(self):
        responses = iter(("", LOG_LINE))
        listener = self._listener_for_responses(responses)

        listener.wait_for_transcript(timeout=0.1)

        fingerprints = tuple(listener._recent_transcripts)
        self.assertEqual(1, len(fingerprints))
        self.assertNotIn("wie geht es dir", repr(fingerprints))
        self.assertEqual(64, len(fingerprints[0]))
        self.assertNotIn(
            "wie geht es dir",
            repr(listener._seen_line_fingerprints),
        )

    def test_invalid_duplicate_window_is_rejected(self):
        for value in (-0.1, 31.0, float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                WirePodTranscriptListener("http://test", duplicate_window=value)

    @staticmethod
    def _listener_for_responses(responses):
        def handle_request(request):
            return httpx.Response(200, text=next(responses))

        client = httpx.Client(
            base_url="http://test",
            transport=httpx.MockTransport(handle_request),
        )
        return WirePodTranscriptListener(
            "http://test",
            poll_interval=0.001,
            client=client,
        )


if __name__ == "__main__":
    unittest.main()
