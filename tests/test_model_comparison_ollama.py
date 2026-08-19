"""Tests for the explicit local model comparison diagnostic."""

import unittest
from unittest.mock import patch

from diagnostics.model_comparison_ollama import _RecordingModel, main


class ModelComparisonTests(unittest.TestCase):
    """Keep model selection explicit and provider delegation unchanged."""

    def test_main_compares_every_explicit_model(self):
        with patch(
            "diagnostics.model_comparison_ollama.compare_model"
        ) as compare:
            result = main(("model-a", "model-b"))

        self.assertEqual(0, result)
        self.assertEqual(
            [("model-a",), ("model-b",)],
            [call.args for call in compare.call_args_list],
        )

    def test_recording_model_retains_delegated_response(self):
        provider = type(
            "Provider",
            (),
            {"generate": lambda self, messages: "Antwort"},
        )()
        recorder = _RecordingModel(provider)

        self.assertEqual("Antwort", recorder.generate(()))
        self.assertEqual(["Antwort"], recorder.responses)


if __name__ == "__main__":
    unittest.main()
