from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv
from genblaze_core import (
    KeyStrategy,
    Modality,
    ObjectStorageSink,
    ParquetSink,
    Pipeline,
    ProviderErrorCode,
)
from genblaze_core.media import SmartEmbedder, get_handler
from genblaze_core.testing import MockProvider
from genblaze_s3 import S3StorageBackend

from dara.ids import new_id
from dara.jobs import B2LiveRunStore, LiveRunRecord, RunAttempt
from dara.ledger import AccountingRecord, write_accounting_record
from dara.pipelines.motion import MotionSpec, build_motion_pipeline
from dara.pipelines.still import _upload_parquet_ledger
from dara.pipelines.voice import VoicePackSpec, build_voice_pipeline
from dara.policy import (
    CostEstimate,
    EnforcementPoint,
    MemoryJobStore,
    PlannedStep,
    Policy,
    PolicyEngine,
    RunPlan,
    Severity,
    StoredDecision,
    money,
)
from dara.projects import B2ProjectStore, Project
from dara.providers import (
    POLICY_REGISTRY,
    ROUTES,
    ImageProviderRouter,
    provider_name_for_model,
    registry_for,
)
from dara.replicate_provider import REPLICATE_IMAGE_MODEL, ReplicateImageProvider
from dara.storage import DaraStorage
from dara.verify import (
    AssetRef,
    HashIndexPointer,
    asset_ref_key,
    hash_index_key,
    manifest_key,
)


PROJECTS = (
    Project(
        project_id="prj_northwind_q3",
        name="Northwind — Q3 campaign",
        client="Northwind Foods",
        policy_id="pol_standard",
        tags=("campaign", "food"),
    ),
    Project(
        project_id="prj_atlas_brand",
        name="Atlas Hotels — Brand film",
        client="Atlas Hotels",
        policy_id="pol_standard",
        tags=("brand", "hospitality"),
    ),
    Project(
        project_id="prj_field_launch",
        name="Field Notes — Product launch",
        client="Field Notes",
        policy_id="pol_standard",
        tags=("launch", "product"),
    ),
)

ACTION_MAXIMUMS = {
    "replicate-fallback": money("0.060000"),
    "voice": money("0.150000"),
    "motion": money("1.700000"),
    "qa-reject": money("0.200000"),
    "blocked": money("0.000000"),
}


@dataclass(frozen=True)
class EvidenceResult:
    action: str
    job_ids: tuple[str, ...]
    actual_cost_usd: Decimal
    saved_cost_usd: Decimal = Decimal("0.000000")
    status: str = "succeeded"


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def require_configuration(*names: str) -> None:
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing required configuration: {', '.join(missing)}")


def storage_sink(staging_dir: Path) -> ObjectStorageSink:
    backend = S3StorageBackend.for_backblaze(
        os.environ["B2_BUCKET"],
        region=os.environ["B2_REGION"],
        key_id=os.environ["B2_KEY_ID"],
        app_key=os.environ["B2_APP_KEY"],
        preflight=True,
    )
    return ObjectStorageSink(
        backend,
        prefix="dara/live",
        key_strategy=KeyStrategy.HIERARCHICAL,
        parquet_sink=ParquetSink(staging_dir),
    )


def seed_policy() -> Policy:
    return Policy(
        policy_id="pol_production_seed",
        name="Production evidence seed",
        description="Operator-only bounded production evidence pass.",
        allowed_providers=frozenset({"openai", "replicate"}),
        allowed_modalities=frozenset({"image", "video", "audio"}),
        allowed_aspect_ratios=frozenset({"1:1", "3:2", "2:3"}),
        max_steps=8,
        max_variants=3,
        max_attempts=1,
        max_duration_s=Decimal("10"),
        max_cost_usd_per_step=money("1.500000"),
        max_cost_usd_per_run=money("2.000000"),
        max_cost_usd_per_day=money("5.000000"),
        require_qa=False,
        require_approval=True,
    )


def locked_policy() -> Policy:
    return seed_policy().model_copy(
        update={
            "policy_id": "pol_locked",
            "name": "Locked down",
            "allowed_modalities": frozenset({"image"}),
            "allowed_aspect_ratios": frozenset({"1:1"}),
            "max_cost_usd_per_step": money("0.020000"),
            "max_cost_usd_per_run": money("0.020000"),
            "max_cost_usd_per_day": money("1.000000"),
        }
    )


def planned_steps(*modalities: Modality) -> tuple[PlannedStep, ...]:
    values: list[PlannedStep] = []
    for modality in modalities:
        route = ROUTES[modality]
        for model in (route.primary_model, *route.fallback_models):
            values.append(
                PlannedStep(
                    provider=provider_name_for_model(model),
                    model=model,
                    modality=modality.value,
                    units=4 if modality is Modality.VIDEO else 1,
                )
            )
    return tuple(values)


async def admit(
    *,
    job_id: str,
    project_id: str,
    modalities: tuple[Modality, ...],
    policy: Policy | None = None,
) -> tuple[PolicyEngine, CostEstimate, StoredDecision]:
    engine = PolicyEngine(MemoryJobStore())
    plan = RunPlan(
        tenant_id="demo",
        job_id=job_id,
        modality=modalities[-1].value,
        aspect_ratio="1:1",
        variants=1,
        max_attempts=1,
        duration_s=Decimal("4") if Modality.VIDEO in modalities else None,
        steps=planned_steps(*modalities),
    )
    estimate, decision = await engine.admit(
        policy or seed_policy(),
        plan,
        POLICY_REGISTRY,
    )
    return engine, estimate, StoredDecision.model_validate(decision)


def content_address(kind: str, sha256: str, extension: str) -> str:
    return f"dara/{kind}/{sha256[:2]}/{sha256[2:4]}/{sha256}{extension}"


def step_cost(step: Any) -> tuple[Decimal, str]:
    if step.cost_usd is not None:
        return money(step.cost_usd), "known"
    if step.modality is Modality.IMAGE:
        if step.model == REPLICATE_IMAGE_MODEL:
            return money("0.040000"), "estimated"
        if step.model.startswith("gpt-image-"):
            return money("0.010000"), "estimated"
    if step.modality is Modality.VIDEO and step.model in {"sora-2", "sora-2-pro"}:
        price = Decimal("0.300000") if step.model == "sora-2-pro" else Decimal("0.100000")
        return money(price * Decimal(str(step.params.get("seconds", 4)))), "estimated"
    if step.modality is Modality.AUDIO and step.model in {"tts-1", "tts-1-hd"}:
        price = Decimal("0.030000") if step.model == "tts-1-hd" else Decimal("0.015000")
        return money(price * Decimal(len(step.prompt or "")) / Decimal(1000)), "estimated"
    return money("0"), "known"


def publish_final_asset(
    storage: DaraStorage,
    result: Any,
    *,
    final_step_index: int,
    actual_cost_usd: Decimal,
    cost_basis: str,
) -> AssetRef:
    run = result.run
    manifest = result.manifest
    step = run.steps[final_step_index]
    source_asset = step.assets[0]
    run_day = run.created_at.astimezone(UTC).date().isoformat()
    prefix = f"dara/live/runs/{run.tenant_id}/{run_day}/{run.run_id}"
    source_key = next(
        key
        for key in storage.list_prefix(prefix)
        if "/assets/" in key and source_asset.asset_id in key
    )
    source_bytes = storage.get_bytes(source_key)
    if source_bytes is None:
        raise RuntimeError("The final source asset is missing from B2.")
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if source_sha256 != source_asset.sha256:
        raise RuntimeError("The final source bytes do not match the Genblaze manifest.")

    extension = Path(source_key).suffix.lower()
    with tempfile.TemporaryDirectory(prefix="dara-evidence-publish-") as temporary:
        source_path = Path(temporary) / f"source{extension}"
        published_path = Path(temporary) / f"published{extension}"
        source_path.write_bytes(source_bytes)
        embedded = SmartEmbedder().embed(
            source_path,
            manifest,
            published_path,
            mime_type=source_asset.media_type,
        )
        if embedded.method != "inline":
            raise RuntimeError(
                f"Expected inline provenance for {source_asset.media_type}, got {embedded.method}."
            )
        handler = get_handler(source_asset.media_type)
        extracted = handler.extract(published_path) if handler is not None else None
        if extracted is None or extracted.canonical_hash != manifest.canonical_hash:
            raise RuntimeError("The published derivative did not re-extract its manifest.")
        published_bytes = published_path.read_bytes()

    published_sha256 = hashlib.sha256(published_bytes).hexdigest()
    source_address = content_address("assets", source_sha256, extension)
    published_address = content_address("published", published_sha256, extension)
    storage.put_bytes(
        source_address,
        source_bytes,
        content_type=source_asset.media_type,
        metadata={"sha256": source_sha256, "run-id": run.run_id},
    )
    storage.put_bytes(
        published_address,
        published_bytes,
        content_type=source_asset.media_type,
        metadata={"sha256": published_sha256, "run-id": run.run_id},
    )
    storage.put_json(manifest_key(run.run_id), manifest)
    reference = AssetRef(
        asset_id=source_asset.asset_id,
        run_id=run.run_id,
        source_sha256=source_sha256,
        published_sha256=published_sha256,
        mime_type=source_asset.media_type,
        bytes=len(published_bytes),
        source_content_address=source_address,
        published_content_address=published_address,
        modality=step.modality.value,
        manifest_embedded=True,
        approved=True,
        cost_usd=f"{actual_cost_usd:.6f}",
        cost_basis=cost_basis,
    )
    storage.put_json(asset_ref_key(reference.asset_id), reference)
    for sha256, hash_kind in (
        (source_sha256, "source"),
        (published_sha256, "published"),
    ):
        storage.put_json(
            hash_index_key(sha256),
            HashIndexPointer(
                sha256=sha256,
                asset_id=reference.asset_id,
                run_id=run.run_id,
                hash_kind=hash_kind,
            ),
        )
    return reference


async def persist_result(
    storage: DaraStorage,
    result: Any,
    *,
    action: str,
    job_id: str,
    project_id: str,
    prompt: str,
    estimate: CostEstimate,
    decision: StoredDecision,
    final_step_index: int,
) -> EvidenceResult:
    pipeline_id = result.run.name or action
    billable: list[tuple[int, Any, Decimal, str]] = []
    for index, step in enumerate(result.run.steps):
        cost, basis = step_cost(step)
        if cost > 0:
            billable.append((index, step, cost, basis))
    actual = money(sum((item[2] for item in billable), start=Decimal("0")))
    basis = "known" if all(item[3] == "known" for item in billable) else "estimated"
    try:
        reference = await asyncio.to_thread(
            publish_final_asset,
            storage,
            result,
            final_step_index=final_step_index,
            actual_cost_usd=actual,
            cost_basis=basis,
        )
    except Exception as exc:
        failed = LiveRunRecord(
            job_id=job_id,
            project_id=project_id,
            pipeline_id=pipeline_id,
            prompt=prompt,
            aspect_ratio="1:1",
            policy_id="pol_production_seed",
            expected_cost_usd=estimate.expected_usd,
            worst_case_cost_usd=estimate.worst_case_usd,
            actual_cost_usd=actual,
            cost_basis=basis,
            status="failed",
            genblaze_run_id=result.run.run_id,
            manifest_hash=result.manifest.canonical_hash,
            policy_decisions=[decision],
            error_code="PUBLISH_FAILED",
            error_message=(
                "Provider work completed, but publication failed. The provider cost is "
                f"still accounted ({type(exc).__name__})."
            ),
            created_at=result.run.created_at,
        )
        failed.append_event(
            "run.failed",
            failed.error_message,
            provider="dara",
            model=f"{pipeline_id}/publish",
        )
        await B2LiveRunStore(storage).put(failed)
        for index, step, cost, step_basis in billable:
            route = ROUTES.get(step.modality)
            write_accounting_record(
                storage,
                AccountingRecord(
                    job_id=f"{job_id}-step-{index + 1}",
                    source_job_id=job_id,
                    genblaze_run_id=result.run.run_id,
                    tenant_id="demo",
                    project_id=project_id,
                    policy_id="pol_production_seed",
                    provider=step.provider or provider_name_for_model(step.model),
                    model=step.model,
                    modality=step.modality.value,
                    primary_model=route.primary_model if route is not None else step.model,
                    failover_count=1 if step.metadata.get("fallback_from") else 0,
                    status="failed",
                    cost_usd=cost,
                    cost_basis=step_basis,
                    approved=False,
                    created_at=result.run.created_at,
                ),
            )
        return EvidenceResult(
            action=action,
            job_ids=(job_id,),
            actual_cost_usd=actual,
            status="failed",
        )
    run = LiveRunRecord(
        job_id=job_id,
        project_id=project_id,
        pipeline_id=pipeline_id,
        prompt=prompt,
        aspect_ratio="1:1",
        policy_id="pol_production_seed",
        expected_cost_usd=estimate.expected_usd,
        worst_case_cost_usd=estimate.worst_case_usd,
        actual_cost_usd=actual,
        cost_basis=basis,
        status="succeeded",
        genblaze_run_id=result.run.run_id,
        asset_id=reference.asset_id,
        manifest_hash=result.manifest.canonical_hash,
        source_sha256=reference.source_sha256,
        published_sha256=reference.published_sha256,
        published_content_address=reference.published_content_address,
        policy_decisions=[decision],
        created_at=result.run.created_at,
    )
    for _, step, cost, step_basis in billable:
        fallback_from = step.metadata.get("fallback_from")
        if fallback_from:
            run.append_event(
                "step.failover",
                f"{fallback_from} failed; {step.model} recovered the production run.",
                provider=step.provider,
                model=step.model,
                at=step.started_at,
            )
        run.append_event(
            "step.completed",
            f"Recorded production step completed at ${cost:.6f} ({step_basis}).",
            provider=step.provider,
            model=step.model,
            at=step.completed_at,
        )
    if len(result.run.steps) == 1:
        final = result.run.steps[0]
        run.attempts = [
            RunAttempt(
                attempt=1,
                genblaze_run_id=result.run.run_id,
                status="approved",
                prompt=final.prompt,
                provider=final.provider,
                model=final.model,
                asset_id=reference.asset_id,
                cost_usd=actual,
                cost_basis=basis,
                created_at=result.run.created_at,
            )
        ]
    run.append_event(
        "run.completed",
        "Production evidence persisted with an embedded manifest and accounting rows.",
        provider="dara",
        model=f"{pipeline_id}/evidence",
    )
    await B2LiveRunStore(storage).put(run)

    final_billable_index = billable[-1][0]
    for index, step, cost, step_basis in billable:
        route = ROUTES.get(step.modality)
        write_accounting_record(
            storage,
            AccountingRecord(
                job_id=f"{job_id}-step-{index + 1}",
                source_job_id=job_id,
                genblaze_run_id=result.run.run_id,
                tenant_id="demo",
                project_id=project_id,
                policy_id="pol_production_seed",
                provider=step.provider or provider_name_for_model(step.model),
                model=step.model,
                modality=step.modality.value,
                primary_model=route.primary_model if route is not None else step.model,
                failover_count=1 if step.metadata.get("fallback_from") else 0,
                status="succeeded",
                cost_usd=cost,
                saved_cost_usd=money("0"),
                cost_basis=step_basis,
                approved=True,
                asset_id=reference.asset_id if index == final_billable_index else None,
                created_at=result.run.created_at,
            ),
        )
    return EvidenceResult(action=action, job_ids=(job_id,), actual_cost_usd=actual)


async def seed_replicate_fallback(storage: DaraStorage) -> EvidenceResult:
    job_id = new_id("job")
    engine, estimate, decision = await admit(
        job_id=job_id,
        project_id="prj_field_launch",
        modalities=(Modality.IMAGE,),
    )
    if decision.outcome is Severity.BLOCK:
        raise RuntimeError(decision.violations[0].message)
    prompt = (
        "A field notebook on warm limestone with one cobalt ribbon, premium editorial "
        "product lighting, no people, logos, words, letters, or watermark."
    )
    with tempfile.TemporaryDirectory(prefix="dara-replicate-fallback-") as temporary:
        root = Path(temporary)
        router = ImageProviderRouter(
            output_dir=root,
            openai_provider=MockProvider(
                name="openai-dalle",
                should_fail=True,
                error_code=ProviderErrorCode.MODEL_ERROR,
                error_message="Deliberate primary-route outage for fallback evidence.",
            ),
            replicate_provider=ReplicateImageProvider(output_dir=root),
            models=registry_for(Modality.IMAGE),
        )
        result = (
            Pipeline(
                "still-campaign",
                tenant_id="demo",
                project_id="prj_field_launch",
            )
            .step(
                router,
                model="gpt-image-2",
                fallback_models=["gpt-image-2-2026-04-21", REPLICATE_IMAGE_MODEL],
                prompt=prompt,
                modality=Modality.IMAGE,
                aspect_ratio="1:1",
                output_format="png",
            )
            .run(
                sink=storage_sink(root / "ledger"),
                timeout=240.0,
                raise_on_failure=False,
            )
        )
        await asyncio.to_thread(_upload_parquet_ledger, storage, root / "ledger")
    evidence = await persist_result(
        storage,
        result,
        action="replicate-fallback",
        job_id=job_id,
        project_id="prj_field_launch",
        prompt=prompt,
        estimate=estimate,
        decision=decision,
        final_step_index=0,
    )
    engine.reservations.settle(job_id, evidence.actual_cost_usd)
    return evidence


async def seed_voice(storage: DaraStorage) -> EvidenceResult:
    results: list[EvidenceResult] = []
    script = "Dara keeps the model, cost, policy decision, and delivered-file hash together."
    voice_projects = tuple(
        zip(
            ("alloy", "coral", "onyx"),
            ("prj_northwind_q3", "prj_atlas_brand", "prj_field_launch"),
            strict=True,
        )
    )
    for voice, project_id in voice_projects:
        job_id = new_id("job")
        engine, estimate, decision = await admit(
            job_id=job_id,
            project_id=project_id,
            modalities=(Modality.AUDIO,),
        )
        if decision.outcome is Severity.BLOCK:
            raise RuntimeError(decision.violations[0].message)
        with tempfile.TemporaryDirectory(prefix=f"dara-voice-{voice}-") as temporary:
            root = Path(temporary)
            result = build_voice_pipeline(
                VoicePackSpec(
                    project_id=project_id,
                    script=script,
                    voices=(voice,),
                ),
                output_dir=root,
            ).run(
                sink=storage_sink(root / "ledger"),
                timeout=150.0,
                raise_on_failure=False,
            )
            await asyncio.to_thread(_upload_parquet_ledger, storage, root / "ledger")
        evidence = await persist_result(
            storage,
            result,
            action="voice",
            job_id=job_id,
            project_id=project_id,
            prompt=script,
            estimate=estimate,
            decision=decision,
            final_step_index=0,
        )
        engine.reservations.settle(job_id, evidence.actual_cost_usd)
        results.append(evidence)
    return EvidenceResult(
        action="voice",
        job_ids=tuple(job for item in results for job in item.job_ids),
        actual_cost_usd=money(sum((item.actual_cost_usd for item in results), Decimal("0"))),
    )


async def seed_motion(storage: DaraStorage) -> EvidenceResult:
    job_id = new_id("job")
    engine, estimate, decision = await admit(
        job_id=job_id,
        project_id="prj_atlas_brand",
        modalities=(Modality.IMAGE, Modality.VIDEO, Modality.AUDIO),
    )
    if decision.outcome is Severity.BLOCK:
        raise RuntimeError(decision.violations[0].message)
    spec = MotionSpec(
        project_id="prj_atlas_brand",
        keyframe_prompt=(
            "A quiet Atlas hotel lobby at blue hour, warm practical lights, polished "
            "stone, premium architectural editorial photography, no people or text."
        ),
        video_prompt=(
            "A slow four-second cinematic push through the same quiet hotel lobby, "
            "subtle parallax, stable architecture, no text or logos."
        ),
        narration="Every generated frame keeps its operational receipt.",
    )
    with tempfile.TemporaryDirectory(prefix="dara-motion-") as temporary:
        root = Path(temporary)
        result = build_motion_pipeline(spec, output_dir=root).run(
            sink=storage_sink(root / "ledger"),
            timeout=360.0,
            pipeline_timeout=480.0,
            raise_on_failure=False,
        )
        await asyncio.to_thread(_upload_parquet_ledger, storage, root / "ledger")
    evidence = await persist_result(
        storage,
        result,
        action="motion",
        job_id=job_id,
        project_id="prj_atlas_brand",
        prompt=spec.video_prompt,
        estimate=estimate,
        decision=decision,
            final_step_index=4,
    )
    engine.reservations.settle(job_id, evidence.actual_cost_usd)
    return evidence


async def seed_qa_reject(storage: DaraStorage) -> EvidenceResult:
    """Run the real still agent against an intentionally exacting QA policy."""

    del storage
    from dara import main as api_main

    policy_id = "pol_qa_reject_evidence"
    qa_policy = seed_policy().model_copy(
        update={
            "policy_id": policy_id,
            "name": "Production QA rejection evidence",
            "description": "Three paid candidates must score perfectly or remain unpublished.",
            "allowed_modalities": frozenset({"image"}),
            "allowed_aspect_ratios": frozenset({"1:1"}),
            "max_steps": 3,
            "max_variants": 1,
            "max_attempts": 3,
            "max_cost_usd_per_run": money("0.250000"),
            "require_qa": True,
            "min_qa_score": 1.0,
            "block_on_qa_failure": False,
        }
    )
    api_main.POLICIES[policy_id] = qa_policy
    job_id = new_id("job")
    run = LiveRunRecord(
        job_id=job_id,
        project_id="prj_field_launch",
        pipeline_id="still-campaign",
        prompt=(
            "Create a square product label with exactly seven centered lines reading: "
            "FIELD NOTES / EDITION 27 / COBALT / 31 JULY 2026 / LOT 0042 / "
            "NO SUBSTITUTIONS / USEDARA.XYZ. Every character must be perfectly legible."
        ),
        aspect_ratio="1:1",
        policy_id=policy_id,
        expected_cost_usd=money("0.070000"),
        worst_case_cost_usd=money("0.200000"),
        cost_basis="estimated",
    )
    run.append_event(
        "run.queued",
        "Production QA-rejection evidence queued under a perfect-score threshold.",
        provider="dara",
        model="qa/v1",
    )
    await api_main.live_run_store.put(run)
    await api_main.execute_live_still(job_id)
    recorded = await api_main.live_run_store.get("demo", job_id)
    if recorded is None:
        raise RuntimeError("The QA evidence run disappeared from the live store.")
    rejected = [attempt for attempt in recorded.attempts if attempt.status == "rejected"]
    if not rejected:
        raise RuntimeError("The exacting QA run produced no rejected paid attempts.")
    if recorded.error_code != "QA_REJECTED":
        recorded.qa_status = "failed"
        recorded.qa_score = rejected[-1].qa_score
        recorded.qa_attempts = len(rejected)
        recorded.qa_issues = [
            "The paid candidate scored below the perfect-score evidence threshold."
        ]
        recorded.error_code = "QA_REJECTED"
        recorded.error_message = (
            "No candidate passed Dara's visual QA gate. Every attempt remains "
            "recorded in B2; the unapproved images were not published."
        )
        await api_main.live_run_store.put(recorded)
    return EvidenceResult(
        action="qa-reject",
        job_ids=(job_id,),
        actual_cost_usd=recorded.actual_cost_usd or money("0"),
        status=recorded.status,
    )


async def seed_blocked(storage: DaraStorage) -> EvidenceResult:
    saved = money("0")
    job_ids: list[str] = []
    for project in PROJECTS:
        job_id = new_id("job")
        _, estimate, decision = await admit(
            job_id=job_id,
            project_id=project.project_id,
            modalities=(Modality.VIDEO,),
            policy=locked_policy(),
        )
        if decision.outcome is not Severity.BLOCK:
            raise RuntimeError("The locked video seed unexpectedly passed policy.")
        run = LiveRunRecord(
            job_id=job_id,
            project_id=project.project_id,
            pipeline_id="motion-spot",
            prompt="A policy-blocked four-second client motion request.",
            aspect_ratio="1:1",
            policy_id="pol_locked",
            expected_cost_usd=estimate.expected_usd,
            worst_case_cost_usd=estimate.worst_case_usd,
            actual_cost_usd=money("0"),
            cost_basis="known",
            status="blocked",
            policy_decisions=[decision],
        )
        run.append_event(
            "policy.blocked",
            f"{decision.violations[0].message} No provider was called; $%s was prevented."
            % estimate.expected_usd,
            provider="dara",
            model="policy/v1",
        )
        await B2LiveRunStore(storage).put(run)
        write_accounting_record(
            storage,
            AccountingRecord(
                job_id=job_id,
                tenant_id="demo",
                project_id=project.project_id,
                policy_id="pol_locked",
                provider="openai",
                model="sora-2",
                modality="video",
                primary_model="sora-2",
                status="blocked",
                cost_usd=money("0"),
                saved_cost_usd=estimate.expected_usd,
                cost_basis="known",
                approved=False,
                created_at=run.created_at,
            ),
        )
        saved = money(saved + estimate.expected_usd)
        job_ids.append(job_id)
    return EvidenceResult(
        action="blocked",
        job_ids=tuple(job_ids),
        actual_cost_usd=money("0"),
        saved_cost_usd=saved,
    )


async def execute(actions: Iterable[str]) -> list[EvidenceResult]:
    require_configuration(
        "OPENAI_API_KEY",
        "REPLICATE_API_TOKEN",
        "B2_KEY_ID",
        "B2_APP_KEY",
        "B2_BUCKET",
        "B2_REGION",
    )
    storage = DaraStorage.from_env()
    project_store = B2ProjectStore(storage)
    for project in PROJECTS:
        await project_store.put(project)
    functions = {
        "replicate-fallback": seed_replicate_fallback,
        "voice": seed_voice,
        "motion": seed_motion,
        "qa-reject": seed_qa_reject,
        "blocked": seed_blocked,
    }
    return [await functions[action](storage) for action in actions]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write real, current production evidence to Dara's B2 ledger.",
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=tuple(ACTION_MAXIMUMS),
        required=True,
        help="Evidence action to execute; repeat for multiple actions.",
    )
    parser.add_argument(
        "--max-spend-usd",
        required=True,
        type=Decimal,
        help="Operator-authorized ceiling; the command refuses a larger plan.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Required acknowledgement that these actions can call paid providers.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv(project_root() / ".env")
    args = parse_args()
    actions = tuple(dict.fromkeys(args.only))
    planned = money(sum((ACTION_MAXIMUMS[item] for item in actions), Decimal("0")))
    ceiling = money(args.max_spend_usd)
    if not args.execute:
        raise SystemExit(
            f"Dry safety stop: requested actions reserve up to ${planned:.6f}. "
            "Pass --execute only after authorizing that ceiling."
        )
    if ceiling <= 0 or planned > ceiling:
        raise SystemExit(
            f"Refusing plan: ${planned:.6f} maximum exceeds ${ceiling:.6f} authorization."
        )
    outcomes = asyncio.run(execute(actions))
    print(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "authorized_ceiling_usd": f"{ceiling:.6f}",
                "planned_maximum_usd": f"{planned:.6f}",
                "actual_recorded_usd": (
                    f"{sum((item.actual_cost_usd for item in outcomes), Decimal('0')):.6f}"
                ),
                "saved_cost_usd": (
                    f"{sum((item.saved_cost_usd for item in outcomes), Decimal('0')):.6f}"
                ),
                "actions": [
                    {
                        "action": item.action,
                        "job_ids": item.job_ids,
                        "actual_cost_usd": f"{item.actual_cost_usd:.6f}",
                        "saved_cost_usd": f"{item.saved_cost_usd:.6f}",
                        "status": item.status,
                    }
                    for item in outcomes
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
