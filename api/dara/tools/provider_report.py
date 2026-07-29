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
    for run in runs:
        all_qa_latencies.extend(qa_latencies(run))
        if run.qa_status == "failed":
            qa_failures += max(1, run.qa_attempts)
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
        step = manifest.run.steps[0]
        if step.model != "gpt-image-2":
            continue
        latency = seconds(step.started_at, step.completed_at)
        if latency is not None:
            image_latencies.append(latency)

    return [
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
