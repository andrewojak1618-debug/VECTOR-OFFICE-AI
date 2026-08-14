import tempfile
import unittest
from pathlib import Path

import httpx

from brain.ollama_runtime import OllamaRuntime


class FakeResponse:
    def raise_for_status(self):
        return None


class SequencedClient:
    def __init__(self, available_states):
        self.available_states = iter(available_states)

    def get(self, url):
        if next(self.available_states):
            return FakeResponse()

        raise httpx.ConnectError("offline")


class OllamaRuntimeTests(unittest.TestCase):
    def test_does_not_launch_when_service_is_already_available(self):
        launches = []
        runtime = OllamaRuntime(
            "http://127.0.0.1:11434",
            client=SequencedClient([True]),
            process_launcher=lambda *args, **kwargs: launches.append(args),
        )

        self.assertTrue(runtime.ensure_available())
        self.assertEqual([], launches)

    def test_launches_configured_executable_and_waits_for_service(self):
        launches = []

        with tempfile.TemporaryDirectory() as temp_directory:
            executable = Path(temp_directory) / "ollama.exe"
            executable.touch()
            runtime = OllamaRuntime(
                "http://127.0.0.1:11434",
                executable=str(executable),
                startup_timeout=0.1,
                poll_interval=0.001,
                client=SequencedClient([False, True]),
                process_launcher=(
                    lambda *args, **kwargs: launches.append((args, kwargs))
                ),
            )

            self.assertTrue(runtime.ensure_available())

        self.assertEqual(str(executable), launches[0][0][0][0])
        self.assertEqual("serve", launches[0][0][0][1])

    def test_returns_false_when_configured_executable_is_missing(self):
        runtime = OllamaRuntime(
            "http://127.0.0.1:11434",
            executable="Z:/missing/ollama.exe",
            client=SequencedClient([False]),
        )

        self.assertFalse(runtime.ensure_available())


if __name__ == "__main__":
    unittest.main()
