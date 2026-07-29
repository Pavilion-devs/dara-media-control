from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dara.pipelines.qa import OpenAIVisionEvaluator
from dara.pipelines.still import (
    ExpandedPrompt,
    PolicyGateRejectedError,
    _publish_result,
    _upload_parquet_ledger,
    expand_brief,
    render_expanded_prompt,
)
from dara.policy import (
    EnforcementPoint,
    MemoryJobStore,
    PolicyEngine,
)
from test_policy import standard_policy


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
    def test_prompt_expansion_is_structured_and_rendered(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_chat(model: str, **kwargs: object) -> SimpleNamespace:
            calls.append({"model": model, **kwargs})
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "visual_prompt": (
                            "A cobalt ceramic cube centered on warm gray linen, "
                            "soft north-window light, restrained editorial finish."
                        ),
                        "negative_constraints": [
                            "no text",
                            "no extra objects",
                        ],
                    }
                )
            )

        expanded = expand_brief(
            "A cobalt cube on a warm gray surface",
            chat_call=fake_chat,
        )

        self.assertIsInstance(expanded, ExpandedPrompt)
        self.assertEqual(calls[0]["model"], "gpt-4.1-mini")
        self.assertIs(calls[0]["response_format"], ExpandedPrompt)
        self.assertEqual(
            render_expanded_prompt(expanded),
            (
                f"{expanded.visual_prompt}\n"
                "Avoid: no text; no extra objects"
            ),
        )
        self.assertEqual(
            set(ExpandedPrompt.model_json_schema()["required"]),
            {"visual_prompt", "negative_constraints"},
        )

    def test_pre_step_hook_runs_before_the_qa_provider_call(self) -> None:
        calls = 0

        def block_before_provider() -> None:
            raise RuntimeError("policy blocked QA")

        def fake_chat(model: str, **kwargs: object) -> SimpleNamespace:
            nonlocal calls
            del model, kwargs
            calls += 1
            return SimpleNamespace(text="{}")

        evaluator = OpenAIVisionEvaluator(
            storage=FakeStorage(),  # type: ignore[arg-type]
            brief="A cobalt cube on a warm gray surface",
            chat_call=fake_chat,
            before_evaluate=block_before_provider,
        )

        with self.assertRaisesRegex(RuntimeError, "policy blocked QA"):
            evaluator.evaluate(result())

        self.assertEqual(calls, 0)

    def test_pre_publish_gate_runs_after_embedding_and_before_b2_writes(self) -> None:
        source = b"source-image"
        source_sha256 = hashlib.sha256(source).hexdigest()
        asset = SimpleNamespace(
            asset_id="ast_candidate",
            media_type="image/png",
            sha256=source_sha256,
        )
        step = SimpleNamespace(
            assets=[asset],
            modality=SimpleNamespace(value="image"),
        )
        run = SimpleNamespace(
            tenant_id="demo",
            run_id="run_candidate",
            created_at=datetime.now(UTC),
            steps=[step],
        )
        result_value = SimpleNamespace(
            run=run,
            manifest=SimpleNamespace(),
        )

        class PublishStorage:
            writes = 0

            def list_prefix(self, prefix: str) -> tuple[str, ...]:
                return (f"{prefix}/assets/ast_candidate.png",)

            def get_bytes(self, key: str) -> bytes:
                del key
                return source

            def put_bytes(self, *args: object, **kwargs: object) -> str:
                del args, kwargs
                self.writes += 1
                return "memory://write"

            def put_json(self, *args: object, **kwargs: object) -> str:
                del args, kwargs
                self.writes += 1
                return "memory://write"

        class Embedder:
            def embed(
                self,
                source_path: Path,
                manifest: object,
                published_path: Path,
                *,
                mime_type: str,
            ) -> SimpleNamespace:
                del manifest, mime_type
                published_path.write_bytes(source_path.read_bytes() + b"-embedded")
                return SimpleNamespace(method="inline")

        storage = PublishStorage()
        engine = PolicyEngine(MemoryJobStore())
        with patch("dara.pipelines.still.SmartEmbedder", return_value=Embedder()):
            with self.assertRaises(PolicyGateRejectedError):
                _publish_result(
                    storage,  # type: ignore[arg-type]
                    result_value,
                    recorded_cost_usd=Decimal("0.015"),
                    cost_basis="estimated",
                    qa_score=0.9,
                    qa_attempts=1,
                    qa_issues=(),
                    pre_publish_gate=lambda embedded: engine.evaluate(
                        EnforcementPoint.PRE_PUBLISH,
                        standard_policy(),
                        approved=False,
                        manifest_embedded=embedded,
                    ),
                )

        self.assertEqual(storage.writes, 0)

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

    def test_parquet_staging_uploads_to_immutable_month_partition(self) -> None:
        uploaded: list[tuple[str, bytes]] = []

        class UploadStorage:
            def put_bytes(
                self,
                key: str,
                data: bytes,
                **kwargs: object,
            ) -> str:
                del kwargs
                uploaded.append((key, data))
                return key

        with tempfile.TemporaryDirectory() as temporary:
            staging = Path(temporary)
            parquet = (
                staging
                / "runs"
                / "dt=2026-07-29"
                / "tenant_id=demo"
                / "modality=image"
                / "provider=openai"
                / "run_ledger.parquet"
            )
            parquet.parent.mkdir(parents=True)
            parquet.write_bytes(b"PAR1-test")
            count = _upload_parquet_ledger(  # type: ignore[arg-type]
                UploadStorage(),
                staging,
            )

        self.assertEqual(count, 1)
        self.assertEqual(
            uploaded[0][0],
            "dara/ledger/runs/year=2026/month=07/run_ledger.parquet",
        )
        self.assertEqual(uploaded[0][1], b"PAR1-test")


if __name__ == "__main__":
    unittest.main()
