from __future__ import annotations

import asyncio
import json
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal

from genblaze_core import Manifest

from dara.jobs import B2LiveRunStore, LiveRunRecord
from dara.storage import DaraStorage
from dara.verify import manifest_key


@dataclass(frozen=True)
class ProviderMeasurement:
    provider: str
    model: str
    modality: str
    samples: int
    successful: int
    failed: int
    p50_latency_s: float | None
    max_latency_s: float | None
    over_90s: bool
    unit_cost_usd: str
    cost_basis: str


def seconds(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return round((end - start).total_seconds(), 3)


def qa_latencies(run: LiveRunRecord) -> list[float]:
    completed_at: datetime | None = None
    values: list[float] = []
    for event in run.events:
        if event.type == "step.completed" and event.model == "gpt-image-2":
            completed_at = event.at
        elif event.type == "agent.iteration.evaluated" and completed_at is not None:
            values.append(round((event.at - completed_at).total_seconds(), 3))
            completed_at = None
    return values


def measurement(
    *,
    provider: str,
    model: str,
    modality: str,
    latencies: list[float],
    failures: int,
    unit_cost_usd: Decimal,
    cost_basis: str,
) -> ProviderMeasurement:
    return ProviderMeasurement(
        provider=provider,
        model=model,
        modality=modality,
        samples=len(latencies) + failures,
        successful=len(latencies),
        failed=failures,
        p50_latency_s=(
            round(statistics.median(latencies), 3) if latencies else None
        ),
        max_latency_s=round(max(latencies), 3) if latencies else None,
        over_90s=any(value > 90 for value in latencies),
        unit_cost_usd=f"{unit_cost_usd:.6f}",
        cost_basis=cost_basis,
    )


async def build_report(
    storage: DaraStorage,
    runs: list[LiveRunRecord],
) -> list[ProviderMeasurement]:
    image_latencies: list[float] = []
    image_failures = 0
    all_qa_latencies: list[float] = []
    qa_failures = 0
    routed: dict[str, tuple[list[float], int]] = {
        "black-forest-labs/flux-1.1-pro": ([], 0),
        "sora-2": ([], 0),
        "tts-1": ([], 0),
    }
    for run in runs:
        run_qa_latencies = qa_latencies(run)
        scored_attempts = [
            attempt for attempt in run.attempts if attempt.qa_score is not None
        ]
        if len(scored_attempts) == len(run_qa_latencies):
            all_qa_latencies.extend(
                latency
                for latency, attempt in zip(
                    run_qa_latencies,
                    scored_attempts,
                    strict=True,
                )
                if attempt.status == "approved"
            )
            qa_failures += sum(
                attempt.status == "rejected" for attempt in scored_attempts
            )
        elif run.qa_status == "failed":
            qa_failures += max(1, run.qa_attempts, len(run_qa_latencies))
        else:
            all_qa_latencies.extend(run_qa_latencies)
        if run.genblaze_run_id is None:
            if run.error_code == "PROVIDER_ERROR":
                image_failures += 1
            continue
        manifest = await asyncio.to_thread(
            storage.get_json,
            manifest_key(run.genblaze_run_id),
            Manifest,
        )
        if manifest is None or not manifest.run.steps:
            continue
        for step in manifest.run.steps:
            latency = seconds(step.started_at, step.completed_at)
            if step.model == "gpt-image-2":
                if latency is not None:
                    image_latencies.append(latency)
                continue
            if step.model not in routed:
                continue
            latencies, failures = routed[step.model]
            if step.status.value == "succeeded" and latency is not None:
                latencies.append(latency)
            else:
                routed[step.model] = (latencies, failures + 1)

    results = [
        measurement(
            provider="openai-dalle",
            model="gpt-image-2",
            modality="image",
            latencies=image_latencies,
            failures=image_failures,
            unit_cost_usd=Decimal("0.010000"),
            cost_basis=(
                "Dara conservative low-quality reservation; the Genblaze adapter "
                "does not expose settled image-token cost"
            ),
        ),
        measurement(
            provider="openai",
            model="gpt-4.1-mini",
            modality="vision-qa",
            latencies=all_qa_latencies,
            failures=qa_failures,
            unit_cost_usd=Decimal("0.005000"),
            cost_basis="Dara conservative structured-evaluation reservation",
        ),
    ]
    specifications = {
        "black-forest-labs/flux-1.1-pro": (
            "replicate",
            "image",
            Decimal("0.040000"),
            "registered per-output price",
        ),
        "sora-2": (
            "openai-sora",
            "video",
            Decimal("0.100000"),
            "registry estimate per output second",
        ),
        "tts-1": (
            "openai-tts",
            "audio",
            Decimal("0.015000"),
            "provider-reported price per 1K input characters",
        ),
    }
    for model, (provider, modality, unit_cost, basis) in specifications.items():
        latencies, failures = routed[model]
        if latencies or failures:
            results.append(
                measurement(
                    provider=provider,
                    model=model,
                    modality=modality,
                    latencies=latencies,
                    failures=failures,
                    unit_cost_usd=unit_cost,
                    cost_basis=basis,
                )
            )
    return results


async def main() -> None:
    storage = DaraStorage.from_env()
    runs = await B2LiveRunStore(storage).list("demo")
    report = await build_report(storage, runs)
    print(
        json.dumps(
            {
                "generated_from": "dara/state/live-runs + trusted manifests",
                "measurements": [asdict(item) for item in report],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
