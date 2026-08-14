import unittest

import httpx

from voice.wirepod_input import WirePodTranscriptListener


LOG_LINE = (
    "2026.08.14 15:30:00: Intent matched: intent_knowledge_promptquestion, "
    "transcribed text: 'wie geht es dir vector', device: 0dd1fd3b"
)
NO_AUDIO_LINE = (
    "2026.08.14 15:29:59: Intent matched: intent_system_noaudio, "
    "transcribed text: '', device: 0dd1fd3b"
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


if __name__ == "__main__":
    unittest.main()
