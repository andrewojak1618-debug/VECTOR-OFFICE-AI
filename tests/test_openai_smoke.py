"""Tests for the explicit, minimal OpenAI connectivity diagnostic."""

import io
import unittest
from contextlib import redirect_stdout

from diagnostics.openai_smoke import run_diagnostic


class StubOpenAIProvider:
    """Return a controlled response or sanitized provider failure."""

    model = "test-model"

    def __init__(self, response="OK", failing=False):
        self.response = response
        self.failing = failing

    def generate(self, _messages):
        if self.failing:
            raise RuntimeError("sanitized failure")
        return self.response


class OpenAISmokeTests(unittest.TestCase):
    def test_non_empty_response_passes(self):
        self.assertTrue(self._run(StubOpenAIProvider()))

    def test_empty_response_fails(self):
        self.assertFalse(self._run(StubOpenAIProvider(response=" ")))

    def test_provider_failure_is_safely_reported(self):
        self.assertFalse(self._run(StubOpenAIProvider(failing=True)))

    @staticmethod
    def _run(provider):
        with redirect_stdout(io.StringIO()):
            return run_diagnostic(provider)


if __name__ == "__main__":
    unittest.main()
