from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from genblaze_core import Manifest, Modality

from dara.ids import new_id
from dara.jobs import B2LiveRunStore, LiveRunRecord
from dara.ledger import AccountingRecord, write_accounting_record
from dara.policy import money
from dara.storage import DaraStorage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Account a known provider-complete run whose Dara publication failed.",
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--cost-usd", required=True, type=Decimal)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


async def backfill(args: argparse.Namespace) -> dict[str, object]:
    if not args.execute:
        raise RuntimeError("Pass --execute after checking the run id and cost.")
    storage = DaraStorage.from_env()
    day = datetime.now(UTC).date().isoformat()
    prefix = f"dara/live/runs/demo/{day}/{args.run_id}"
    manifest_key = next(
        key for key in storage.list_prefix(prefix) if key.endswith("/manifest.json")
    )
    data = storage.get_bytes(manifest_key)
    if data is None:
        raise RuntimeError("The trusted Genblaze manifest is missing.")
    manifest = Manifest.model_validate_json(data)
    if (
        manifest.run.run_id != args.run_id
        or not manifest.verify_hash()
        or not manifest.verify()
    ):
        raise RuntimeError("The selected Genblaze manifest is not trusted.")
    step = manifest.run.steps[0]
    cost = money(args.cost_usd)
    job_id = new_id("job")
    pipeline_id = manifest.run.name or "voiceover-pack"
    run = LiveRunRecord(
        job_id=job_id,
        project_id=args.project_id,
        pipeline_id=pipeline_id,
        prompt=step.prompt or "Recorded provider attempt",
        aspect_ratio="1:1",
        policy_id="pol_production_seed",
        expected_cost_usd=cost,
        worst_case_cost_usd=cost,
        actual_cost_usd=cost,
        cost_basis="known",
        status="failed",
        genblaze_run_id=manifest.run.run_id,
        manifest_hash=manifest.canonical_hash,
        error_code="PUBLISH_FAILED",
        error_message=(
            "Provider work completed, but the downstream pipeline or publication step "
            "failed. The paid attempt remains accounted."
        ),
        created_at=manifest.run.created_at,
    )
    run.append_event(
        "run.failed",
        run.error_message,
        provider="dara",
        model=f"{pipeline_id}/publish",
    )
    await B2LiveRunStore(storage).put(run)
    primary = "tts-1" if step.modality is Modality.AUDIO else step.model
    write_accounting_record(
        storage,
        AccountingRecord(
            job_id=job_id,
            source_job_id=job_id,
            genblaze_run_id=manifest.run.run_id,
            tenant_id="demo",
            project_id=args.project_id,
            policy_id="pol_production_seed",
            provider=step.provider or "openai",
            model=step.model,
            modality=step.modality.value,
            primary_model=primary,
            status="failed",
            cost_usd=cost,
            cost_basis="known",
            approved=False,
            created_at=manifest.run.created_at,
        ),
    )
    return {"job_id": job_id, "run_id": args.run_id, "cost_usd": f"{cost:.6f}"}


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    print(json.dumps(asyncio.run(backfill(parse_args())), indent=2))


if __name__ == "__main__":
    main()
