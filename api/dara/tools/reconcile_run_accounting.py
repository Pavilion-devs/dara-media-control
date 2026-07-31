from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from genblaze_core import Manifest

from dara.jobs import B2LiveRunStore
from dara.ledger import AccountingRecord, write_accounting_record
from dara.policy import money
from dara.providers import ROUTES, provider_name_for_model
from dara.storage import DaraStorage
from dara.tools.seed_production_evidence import step_cost
from dara.verify import manifest_key


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute one trusted production run's per-step accounting.",
    )
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


async def reconcile(job_id: str, *, execute: bool) -> dict[str, object]:
    if not execute:
        raise RuntimeError("Pass --execute after checking the target job id.")
    storage = DaraStorage.from_env()
    store = B2LiveRunStore(storage)
    run = await store.get("demo", job_id)
    if run is None or run.status != "succeeded" or run.genblaze_run_id is None:
        raise RuntimeError("The target is not a succeeded trusted live run.")
    manifest = storage.get_json(manifest_key(run.genblaze_run_id), Manifest)
    if manifest is None or not manifest.verify_hash() or not manifest.verify():
        raise RuntimeError("The target manifest is missing or untrusted.")

    resolved: list[tuple[int, object, Decimal, str]] = []
    for index, step in enumerate(manifest.run.steps):
        cost, basis = step_cost(step)
        resolved.append((index, step, cost, basis))
    actual = money(sum((item[2] for item in resolved), Decimal("0")))
    overall_basis = (
        "known" if all(item[3] == "known" for item in resolved) else "estimated"
    )
    final_index = len(resolved) - 1
    for index, step, cost, basis in resolved:
        route = ROUTES.get(step.modality)
        write_accounting_record(
            storage,
            AccountingRecord(
                job_id=f"{job_id}-step-{index + 1}",
                source_job_id=job_id,
                genblaze_run_id=manifest.run.run_id,
                tenant_id=run.tenant_id,
                project_id=run.project_id,
                policy_id=run.policy_id,
                provider=step.provider or provider_name_for_model(step.model),
                model=step.model,
                modality=step.modality.value,
                primary_model=route.primary_model if route is not None else step.model,
                failover_count=1 if step.metadata.get("fallback_from") else 0,
                status="succeeded",
                cost_usd=cost,
                cost_basis=basis,
                approved=True,
                asset_id=run.asset_id if index == final_index else None,
                created_at=manifest.run.created_at.astimezone(UTC),
            ),
        )
    run.actual_cost_usd = actual
    run.cost_basis = overall_basis
    run.append_event(
        "accounting.reconciled",
        "Recomputed provider spend without assigning prices to local FFmpeg steps.",
        provider="dara",
        model="accounting/v1",
    )
    await store.put(run)
    return {
        "job_id": job_id,
        "actual_cost_usd": f"{actual:.6f}",
        "steps": [
            {
                "model": step.model,
                "cost_usd": f"{cost:.6f}",
                "basis": basis,
            }
            for _, step, cost, basis in resolved
        ],
    }


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    args = parse_args()
    print(json.dumps(asyncio.run(reconcile(args.job_id, execute=args.execute)), indent=2))


if __name__ == "__main__":
    main()
