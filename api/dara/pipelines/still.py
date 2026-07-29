from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from genblaze_core import (
    AgentLoop,
    KeyStrategy,
    Manifest,
    Modality,
    ObjectStorageSink,
    ParquetSink,
    Pipeline,
    PipelineResult,
)
from genblaze_core.media import SmartEmbedder
from genblaze_s3 import S3StorageBackend

from ..policy import (
    CostEstimate,
    Decision,
    EnforcementPoint,
    Policy,
    PolicyEngine,
    Severity,
    money,
)
from ..providers import provider_for, route_for
from ..storage import DaraStorage
from ..verify import (
    AssetRef,
    HashIndexPointer,
    asset_ref_key,
    hash_index_key,
    manifest_key,
)
from .qa import OpenAIVisionEvaluator


ASPECT_SIZES = {
    "1:1": "1024x1024",
    "3:2": "1536x1024",
    "2:3": "1024x1536",
}


@dataclass(frozen=True)
class StillPipelineOutput:
    run_id: str
    asset_id: str
    manifest_hash: str
    source_sha256: str
    published_sha256: str
    published_content_address: str
    actual_cost_usd: Decimal
    cost_basis: Literal["known", "estimated"]
    qa_score: float
    qa_attempts: int
    qa_issues: tuple[str, ...]
    policy_decisions: tuple[Decision, ...] = ()


class QARejectedError(RuntimeError):
    def __init__(
        self,
        *,
        score: float | None,
        attempts: int,
        issues: tuple[str, ...],
        actual_cost_usd: Decimal,
        policy_decisions: tuple[Decision, ...] = (),
    ) -> None:
        super().__init__("No generated candidate passed Dara's visual QA gate.")
        self.score = score
        self.attempts = attempts
        self.issues = issues
        self.actual_cost_usd = actual_cost_usd
        self.policy_decisions = policy_decisions


class PolicyGateRejectedError(RuntimeError):
    def __init__(
        self,
        *,
        decisions: tuple[Decision, ...],
        actual_cost_usd: Decimal,
    ) -> None:
        blocking = next(
            (
                violation
                for decision in decisions
                for violation in decision.violations
                if violation.severity is Severity.BLOCK
            ),
            None,
        )
        super().__init__(
            blocking.message
            if blocking is not None
            else "A policy gate rejected the live run."
        )
        self.decisions = decisions
        self.actual_cost_usd = money(actual_cost_usd)


EventCallback = Callable[[dict[str, object]], Awaitable[None]]
AttemptCallback = Callable[[dict[str, object]], Awaitable[None]]
PublishGate = Callable[[bool], Decision]


def _content_address(kind: str, sha256: str, extension: str) -> str:
    return f"dara/{kind}/{sha256[:2]}/{sha256[2:4]}/{sha256}{extension}"


def _upload_parquet_ledger(storage: DaraStorage, staging_dir: Path) -> int:
    uploaded = 0
    for path in sorted(staging_dir.rglob("*.parquet")):
        relative = path.relative_to(staging_dir)
        table = relative.parts[0]
        date_part = next(
            (
                part.removeprefix("dt=")
                for part in relative.parts
                if part.startswith("dt=")
            ),
            datetime.now(UTC).date().isoformat(),
        )
        year, month, _ = date_part.split("-", maxsplit=2)
        key = (
            f"dara/ledger/{table}/year={year}/month={month}/"
            f"{path.stem}.parquet"
        )
        storage.put_bytes(
            key,
            path.read_bytes(),
            content_type="application/vnd.apache.parquet",
            metadata={"run-id": path.stem, "table": table},
        )
        uploaded += 1
    return uploaded


def _event_payload(event: object) -> dict[str, object]:
    values = vars(event)
    event_type = str(values.get("type", "pipeline.event"))
    provider = values.get("provider")
    model = values.get("model")
    timestamp = values.get("timestamp")
    data = values.get("data")
    status = data.get("status") if isinstance(data, dict) else None
    iteration = values.get("iteration")
    total = values.get("total")
    score = values.get("score")
    passed = values.get("passed")
    iterations = values.get("iterations")
    messages = {
        "pipeline.started": "Genblaze pipeline started.",
        "step.started": f"{provider or 'Provider'} / {model or 'model'} started.",
        "step.completed": f"{provider or 'Provider'} / {model or 'model'} completed.",
        "pipeline.completed": "Genblaze manifest sealed.",
        "pipeline.failed": "The Genblaze pipeline failed.",
        "agent.iteration.started": (
            f"Visual QA attempt {int(iteration) + 1}/{total} started."
            if isinstance(iteration, int)
            else "Visual QA attempt started."
        ),
        "agent.iteration.evaluated": (
            f"Visual QA {'passed' if passed else 'requested a revision'}"
            + (f" at {float(score):.2f}." if score is not None else ".")
        ),
        "agent.completed": (
            f"Visual QA loop {'passed' if passed else 'stopped without approval'}"
            + (f" after {iterations} attempt(s)." if iterations is not None else ".")
        ),
    }
    if event_type == "step.progress" and status:
        message = f"{provider or 'Provider'} reported {status}."
    else:
        message = messages.get(event_type, event_type.replace(".", " ").title())
    if event_type.startswith("agent."):
        provider = "openai"
        model = os.getenv("DARA_QA_MODEL", "gpt-4.1-mini")
    return {
        "type": event_type,
        "at": timestamp if isinstance(timestamp, datetime) else datetime.now(UTC),
        "provider": str(provider) if provider else None,
        "model": str(model) if model else None,
        "message": message,
    }


def _publish_result(
    storage: DaraStorage,
    result: Any,
    *,
    recorded_cost_usd: Decimal,
    cost_basis: Literal["known", "estimated"],
    qa_score: float,
    qa_attempts: int,
    qa_issues: tuple[str, ...],
    pre_publish_gate: PublishGate,
) -> StillPipelineOutput:
    run = result.run
    manifest = result.manifest
    step = run.steps[0]
    source_asset = step.assets[0]
    run_day = (run.created_at or datetime.now(UTC)).astimezone(UTC).date().isoformat()
    run_prefix = f"dara/live/runs/{run.tenant_id}/{run_day}/{run.run_id}"
    keys = storage.list_prefix(run_prefix)
    source_key = next(
        key
        for key in keys
        if "/assets/" in key and source_asset.asset_id in key
    )
    source_bytes = storage.get_bytes(source_key)
    if source_bytes is None:
        raise RuntimeError("The generated source asset is missing from trusted storage.")

    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if source_sha256 != source_asset.sha256:
        raise RuntimeError("The generated source bytes do not match the Genblaze manifest.")

    extension = Path(source_key).suffix.lower() or ".png"
    mime_type = source_asset.media_type
    with tempfile.TemporaryDirectory(prefix="dara-live-publish-") as temporary:
        source_path = Path(temporary) / f"source{extension}"
        published_path = Path(temporary) / f"published{extension}"
        source_path.write_bytes(source_bytes)
        embedded = SmartEmbedder().embed(
            source_path,
            manifest,
            published_path,
            mime_type=mime_type,
        )
        if embedded.method != "inline":
            raise RuntimeError("Dara could not embed the manifest into the deliverable.")
        published_bytes = published_path.read_bytes()

    publish_decision = pre_publish_gate(embedded.method == "inline")
    if publish_decision.outcome is Severity.BLOCK:
        raise PolicyGateRejectedError(
            decisions=(publish_decision,),
            actual_cost_usd=recorded_cost_usd,
        )

    published_sha256 = hashlib.sha256(published_bytes).hexdigest()
    source_content_address = _content_address("assets", source_sha256, extension)
    published_content_address = _content_address(
        "published",
        published_sha256,
        extension,
    )
    storage.put_bytes(
        source_content_address,
        source_bytes,
        content_type=mime_type,
        metadata={"sha256": source_sha256, "run-id": run.run_id},
    )
    storage.put_bytes(
        published_content_address,
        published_bytes,
        content_type=mime_type,
        metadata={"sha256": published_sha256, "run-id": run.run_id},
    )
    storage.put_json(manifest_key(run.run_id), manifest)

    actual_cost = recorded_cost_usd.quantize(Decimal("0.000001"))
    reference = AssetRef(
        asset_id=source_asset.asset_id,
        run_id=run.run_id,
        source_sha256=source_sha256,
        published_sha256=published_sha256,
        mime_type=mime_type,
        bytes=len(published_bytes),
        source_content_address=source_content_address,
        published_content_address=published_content_address,
        modality=step.modality.value,
        manifest_embedded=True,
        approved=True,
        cost_usd=f"{actual_cost:.6f}",
        cost_basis=cost_basis,
    )
    storage.put_json(asset_ref_key(source_asset.asset_id), reference)
    for sha256, hash_kind in (
        (source_sha256, "source"),
        (published_sha256, "published"),
    ):
        storage.put_json(
            hash_index_key(sha256),
            HashIndexPointer(
                sha256=sha256,
                asset_id=source_asset.asset_id,
                run_id=run.run_id,
                hash_kind=hash_kind,
            ),
        )

    return StillPipelineOutput(
        run_id=run.run_id,
        asset_id=source_asset.asset_id,
        manifest_hash=manifest.canonical_hash,
        source_sha256=source_sha256,
        published_sha256=published_sha256,
        published_content_address=published_content_address,
        actual_cost_usd=actual_cost,
        cost_basis=cost_basis,
        qa_score=qa_score,
        qa_attempts=qa_attempts,
        qa_issues=qa_issues,
        policy_decisions=(publish_decision,),
    )


async def run_still_pipeline(
    *,
    tenant_id: str,
    project_id: str,
    prompt: str,
    aspect_ratio: str,
    estimated_cost_usd: Decimal,
    generation_cost_usd: Decimal,
    qa_cost_usd: Decimal,
    policy: Policy,
    policy_engine: PolicyEngine,
    on_event: EventCallback,
    on_attempt: AttemptCallback | None = None,
    parent_manifest: Manifest | None = None,
) -> StillPipelineOutput:
    required = (
        "OPENAI_API_KEY",
        "B2_KEY_ID",
        "B2_APP_KEY",
        "B2_BUCKET",
        "B2_REGION",
    )
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            f"Live generation is missing configuration: {', '.join(missing)}"
        )
    try:
        size = ASPECT_SIZES[aspect_ratio]
    except KeyError as exc:
        raise ValueError(f"Unsupported image aspect ratio: {aspect_ratio}") from exc

    result = None
    qa_passed = False
    qa_attempts = 0
    attempt_number = 0
    current_run_id: str | None = None
    current_prompt: str | None = None
    policy_decisions: list[Decision] = []
    estimate = CostEstimate(
        expected_usd=estimated_cost_usd,
        worst_case_usd=money(estimated_cost_usd * policy.max_attempts),
        per_step_usd=(estimated_cost_usd,),
        unpriced_models=(),
    )
    with tempfile.TemporaryDirectory(prefix="dara-live-still-") as output_dir:
        storage = DaraStorage.from_env()
        staging_dir = Path(output_dir) / "ledger"
        backend = S3StorageBackend.for_backblaze(
            os.environ["B2_BUCKET"],
            region=os.environ["B2_REGION"],
            key_id=os.environ["B2_KEY_ID"],
            app_key=os.environ["B2_APP_KEY"],
            preflight=True,
        )
        sink = ObjectStorageSink(
            backend,
            prefix="dara/live",
            key_strategy=KeyStrategy.HIERARCHICAL,
            parquet_sink=ParquetSink(staging_dir),
        )
        current_attempt = 0

        def pre_step(
            *,
            actual_cost: Decimal,
            step_cost: Decimal,
        ) -> None:
            resolved = policy_engine.evaluate(
                EnforcementPoint.PRE_STEP,
                policy,
                estimate=estimate,
                actual_cost=actual_cost,
                step_cost=step_cost,
            )
            policy_decisions.append(resolved)
            if resolved.outcome is Severity.BLOCK:
                raise PolicyGateRejectedError(
                    decisions=tuple(policy_decisions),
                    actual_cost_usd=actual_cost,
                )

        def before_qa() -> None:
            pre_step(
                actual_cost=money(
                    estimated_cost_usd * (current_attempt - 1)
                    + generation_cost_usd
                ),
                step_cost=qa_cost_usd,
            )

        evaluator = OpenAIVisionEvaluator(
            storage=storage,
            brief=prompt,
            threshold=policy.min_qa_score,
            before_evaluate=before_qa,
        )

        def pipeline_factory(context: Any) -> Pipeline:
            nonlocal current_attempt, current_prompt
            current_attempt = len(context.prior_results) + 1
            actual_before_attempt = money(
                estimated_cost_usd * len(context.prior_results)
            )
            pre_step(
                actual_cost=actual_before_attempt,
                step_cost=generation_cost_usd,
            )
            candidate_prompt = (
                context.last_evaluation.feedback
                if context.last_evaluation is not None
                and context.last_evaluation.feedback
                else prompt
            )
            current_prompt = candidate_prompt
            provider = provider_for(
                Modality.IMAGE,
                output_dir=output_dir,
                http_timeout=180.0,
            )
            route = route_for(Modality.IMAGE)
            pipeline = Pipeline(
                "still-campaign",
                tenant_id=tenant_id,
                project_id=project_id,
            ).step(
                provider,
                model=route.primary_model,
                fallback_models=list(route.fallback_models),
                prompt=candidate_prompt,
                modality=Modality.IMAGE,
                size=size,
                quality="low",
                output_format="png",
                n=1,
            )
            if not context.prior_results and parent_manifest is not None:
                pipeline.from_result(
                    PipelineResult(parent_manifest.run, parent_manifest)
                )
            return pipeline
        agent = AgentLoop(
            pipeline_factory,
            evaluator,
            max_iterations=3,
            stop_on_pipeline_failure=True,
        )
        sink._close_with_run = False
        try:
            async for event in agent.astream(
                sink=sink,
                timeout=180.0,
                pipeline_timeout=240.0,
                raise_on_failure=True,
            ):
                await on_event(_event_payload(event))
                event_type = getattr(event, "type", None)
                if event_type == "pipeline.started":
                    attempt_number += 1
                    current_run_id = str(getattr(event, "run_id"))
                    if on_attempt is not None:
                        await on_attempt(
                            {
                                "attempt": attempt_number,
                                "genblaze_run_id": current_run_id,
                                "parent_run_id": (
                                    parent_manifest.run.run_id
                                    if attempt_number == 1
                                    and parent_manifest is not None
                                    else None
                                ),
                                "status": "running",
                                "prompt": current_prompt,
                                "provider": "openai",
                                "model": "gpt-image-2",
                                "created_at": getattr(
                                    event,
                                    "timestamp",
                                    datetime.now(UTC),
                                ),
                            }
                        )
                elif event_type == "agent.iteration.evaluated":
                    post_step = policy_engine.evaluate(
                        EnforcementPoint.POST_STEP,
                        policy,
                        qa_score=(
                            float(getattr(event, "score"))
                            if getattr(event, "score", None) is not None
                            else None
                        ),
                        attempts=int(getattr(event, "iteration", 0)) + 1,
                    )
                    policy_decisions.append(post_step)
                    attempt_result = getattr(event, "result", None)
                    if attempt_result is not None and on_attempt is not None:
                        attempt_run = attempt_result.run
                        step = attempt_run.steps[0]
                        await on_attempt(
                            {
                                "attempt": int(getattr(event, "iteration", 0)) + 1,
                                "genblaze_run_id": attempt_run.run_id,
                                "parent_run_id": attempt_run.parent_run_id,
                                "status": (
                                    "approved"
                                    if bool(getattr(event, "passed", False))
                                    else "rejected"
                                ),
                                "prompt": step.prompt,
                                "provider": step.provider,
                                "model": step.model,
                                "qa_score": getattr(event, "score", None),
                                "asset_id": (
                                    step.assets[0].asset_id
                                    if step.assets
                                    else None
                                ),
                                "created_at": attempt_run.created_at,
                            }
                        )
                    if post_step.outcome is Severity.BLOCK:
                        raise PolicyGateRejectedError(
                            decisions=tuple(policy_decisions),
                            actual_cost_usd=money(
                                estimated_cost_usd
                                * (int(getattr(event, "iteration", 0)) + 1)
                            ),
                        )
                elif event_type in {"pipeline.failed", "step.failed"}:
                    failed_run_id = getattr(event, "run_id", None) or current_run_id
                    if failed_run_id is not None and on_attempt is not None:
                        await on_attempt(
                            {
                                "attempt": max(1, attempt_number),
                                "genblaze_run_id": str(failed_run_id),
                                "parent_run_id": (
                                    parent_manifest.run.run_id
                                    if attempt_number == 1
                                    and parent_manifest is not None
                                    else None
                                ),
                                "status": "failed",
                                "prompt": current_prompt,
                                "provider": getattr(event, "provider", "openai"),
                                "model": getattr(event, "model", "gpt-image-2"),
                                "created_at": getattr(
                                    event,
                                    "timestamp",
                                    datetime.now(UTC),
                                ),
                            }
                        )
                if event_type == "agent.completed":
                    result = getattr(event, "result", None)
                    qa_passed = bool(getattr(event, "passed", False))
                    qa_attempts = int(getattr(event, "iterations", 0))
        finally:
            await asyncio.to_thread(sink.close)
        ledger_files = await asyncio.to_thread(
            _upload_parquet_ledger,
            storage,
            staging_dir,
        )
        await on_event(
            {
                "type": "ledger.uploaded",
                "at": datetime.now(UTC),
                "provider": "backblaze",
                "model": "parquet/v1",
                "message": (
                    f"Uploaded {ledger_files} immutable Parquet ledger file(s) to B2."
                ),
            }
        )

    if result is None:
        raise RuntimeError("The image QA pipeline finished without a result.")
    latest_score = evaluator.evaluations[-1] if evaluator.evaluations else None
    qa_issues = tuple(latest_score.issues) if latest_score else ()
    if not qa_passed or latest_score is None:
        raise QARejectedError(
            score=latest_score.overall if latest_score else None,
            attempts=qa_attempts,
            issues=qa_issues,
            actual_cost_usd=estimated_cost_usd * max(1, qa_attempts),
            policy_decisions=tuple(policy_decisions),
        )
    await on_event(
        {
            "type": "publish.started",
            "at": datetime.now(UTC),
            "provider": "dara",
            "model": "publish/v1",
            "message": "Embedding the manifest and recording the published hash.",
        }
    )
    try:
        output = await asyncio.to_thread(
            _publish_result,
            DaraStorage.from_env(),
            result,
            recorded_cost_usd=estimated_cost_usd * max(1, qa_attempts),
            cost_basis="estimated",
            qa_score=latest_score.overall,
            qa_attempts=qa_attempts,
            qa_issues=qa_issues,
            pre_publish_gate=lambda embedded: policy_engine.evaluate(
                EnforcementPoint.PRE_PUBLISH,
                policy,
                approved=qa_passed,
                manifest_embedded=embedded,
            ),
        )
    except PolicyGateRejectedError as exc:
        raise PolicyGateRejectedError(
            decisions=tuple(policy_decisions) + exc.decisions,
            actual_cost_usd=exc.actual_cost_usd,
        ) from exc
    await on_event(
        {
            "type": "publish.completed",
            "at": datetime.now(UTC),
            "provider": "backblaze",
            "model": "b2/private",
            "message": "Published derivative and trusted hash index committed to B2.",
        }
    )
    return replace(
        output,
        policy_decisions=(
            tuple(policy_decisions) + output.policy_decisions
        ),
    )
