from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from dara.pipelines.qa import OpenAIVisionEvaluator


class FakeStorage:
    def list_prefix(self, prefix: str) -> tuple[str, ...]:
        return (f"{prefix}/assets/ast_candidate.png",)

    def get_bytes(self, key: str) -> bytes:
        del key
        return b"candidate-image"


def result() -> SimpleNamespace:
    asset = SimpleNamespace(asset_id="ast_candidate", media_type="image/png")
    step = SimpleNamespace(
        assets=[asset],
        prompt="A cobalt cube on a warm gray surface",
    )
    run = SimpleNamespace(
        tenant_id="demo",
        run_id="run_candidate",
        created_at=datetime.now(UTC),
        steps=[step],
    )
    return SimpleNamespace(run=run)


class VisionEvaluatorTests(unittest.TestCase):
    def test_structured_score_passes_and_preserves_feedback(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_chat(model: str, **kwargs: object) -> SimpleNamespace:
            calls.append({"model": model, **kwargs})
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "prompt_adherence": 0.94,
                        "technical_quality": 0.91,
                        "brand_fit": 0.85,
                        "usable_as_is": 0.88,
                        "overall": 0.9,
                        "issues": [],
                        "revised_prompt": "Keep the cobalt cube and warm gray surface.",
                    }
                )
            )

        evaluator = OpenAIVisionEvaluator(
            storage=FakeStorage(),  # type: ignore[arg-type]
            brief="A cobalt cube on a warm gray surface",
            chat_call=fake_chat,
        )
        evaluation = evaluator.evaluate(result())

        self.assertTrue(evaluation.passed)
        self.assertEqual(evaluation.score, 0.9)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["model"], "gpt-4.1-mini")
        messages = calls[0]["messages"]
        self.assertIn("data:image/png;base64", str(messages))

    def test_invalid_json_retries_once_then_fails_closed(self) -> None:
        calls = 0

        def fake_chat(model: str, **kwargs: object) -> SimpleNamespace:
            nonlocal calls
            del model, kwargs
            calls += 1
            return SimpleNamespace(text="not valid json")

        evaluator = OpenAIVisionEvaluator(
            storage=FakeStorage(),  # type: ignore[arg-type]
            brief="A cobalt cube on a warm gray surface",
            chat_call=fake_chat,
        )
        evaluation = evaluator.evaluate(result())

        self.assertFalse(evaluation.passed)
        self.assertEqual(evaluation.score, 0.5)
        self.assertEqual(calls, 2)
        self.assertEqual(evaluator.parse_failures, 1)


if __name__ == "__main__":
    unittest.main()
