from __future__ import annotations

import json
from pathlib import Path
from typing import Any


GENERATED_AT = "2026-07-29T20:15:00Z"


def event(
    at_ms: int,
    event_type: str,
    provider: str,
    model: str,
    message: str,
) -> dict[str, Any]:
    return {
        "at_ms": at_ms,
        "type": event_type,
        "provider": provider,
        "model": model,
        "message": message,
    }


def short_events(
    *,
    provider: str,
    model: str,
    pipeline: str,
    outcome: str = "succeeded",
) -> list[dict[str, Any]]:
    return [
        event(0, "policy.allowed", "dara", "policy/v1", "Pre-flight policy allowed."),
        event(
            800,
            "step.started",
            provider,
            model,
            f"{pipeline} provider step started.",
        ),
        event(
            18_000,
            "run.completed" if outcome == "succeeded" else "run.failed",
            "dara",
            pipeline,
            (
                "Run completed and its immutable record was sealed."
                if outcome == "succeeded"
                else "Run stopped with its failed attempt preserved."
            ),
        ),
    ]


def build_corpus() -> dict[str, Any]:
    runs: list[dict[str, Any]] = [
        {
            "seed_id": "seed_still_qa_revision",
            "pipeline_id": "still-campaign",
            "title": "Seeded QA loop fixture · deterministic",
            "project_id": "prj_northwind",
            "policy_id": "pol_standard",
            "brief": (
                "Hero shot of a ceramic bowl on washed linen, morning light, "
                "quiet editorial composition"
            ),
            "provider": "genblaze-testing",
            "model": "mock-image-v1",
            "outcome": "succeeded",
            "approved": True,
            "qa_score": 0.92,
            "qa_attempts": 2,
            "cost_usd": "0.000000",
            "saved_cost_usd": "0.000000",
            "asset_url": "/dara-verified-sample.png",
            "events": [
                event(
                    0,
                    "policy.allowed",
                    "dara",
                    "policy/v1",
                    "Pre-flight allowed with a $0.060000 worst-case reservation.",
                ),
                event(
                    280,
                    "prompt.expansion.completed",
                    "genblaze-testing",
                    "mock-chat-v1",
                    "Fixture brief expanded into a structured production prompt.",
                ),
                event(
                    900,
                    "step.started",
                    "genblaze-testing",
                    "mock-image-v1",
                    "First deterministic image candidate started.",
                ),
                event(
                    23_400,
                    "step.completed",
                    "genblaze-testing",
                    "mock-image-v1",
                    "First deterministic image candidate completed.",
                ),
                event(
                    28_900,
                    "agent.iteration.evaluated",
                    "genblaze-testing",
                    "mock-vision-v1",
                    "Vision QA scored 0.58; linen texture and rim detail needed revision.",
                ),
                event(
                    29_500,
                    "qa.revised",
                    "genblaze",
                    "AgentLoop",
                    "Prompt revised; second attempt linked by parent_run_id.",
                ),
                event(
                    53_000,
                    "step.completed",
                    "genblaze-testing",
                    "mock-image-v1",
                    "Revised deterministic image candidate completed.",
                ),
                event(
                    58_500,
                    "agent.iteration.evaluated",
                    "genblaze-testing",
                    "mock-vision-v1",
                    "Vision QA passed at 0.92.",
                ),
                event(
                    61_000,
                    "publish.completed",
                    "genblaze-testing",
                    "fixture-store/v1",
                    "Fixture source, manifest, and ledger record sealed locally.",
                ),
            ],
        },
        {
            "seed_id": "seed_still_product",
            "pipeline_id": "still-campaign",
            "title": "Product still · first-pass approval",
            "project_id": "prj_field_notes",
            "policy_id": "pol_standard",
            "brief": "Graphite notebook on raw oak with clean directional light.",
            "provider": "genblaze-testing",
            "model": "mock-image-v1",
            "outcome": "succeeded",
            "approved": True,
            "qa_score": 0.95,
            "qa_attempts": 1,
            "cost_usd": "0.000000",
            "saved_cost_usd": "0.000000",
            "asset_url": "/dara-verified-sample.png",
            "events": short_events(
                provider="genblaze-testing",
                model="mock-image-v1",
                pipeline="still-campaign",
            ),
        },
        {
            "seed_id": "seed_still_portrait",
            "pipeline_id": "still-campaign",
            "title": "Portrait crop · approved",
            "project_id": "prj_atlas",
            "policy_id": "pol_permissive",
            "brief": "Architectural hotel portrait with warm evening window light.",
            "provider": "genblaze-testing",
            "model": "mock-image-v1",
            "outcome": "succeeded",
            "approved": True,
            "qa_score": 0.88,
            "qa_attempts": 1,
            "cost_usd": "0.000000",
            "saved_cost_usd": "0.000000",
            "asset_url": "/dara-verified-sample.png",
            "events": short_events(
                provider="genblaze-testing",
                model="mock-image-v1",
                pipeline="still-campaign",
            ),
        },
        {
            "seed_id": "seed_blocked_budget",
            "pipeline_id": "still-campaign",
            "title": "Locked policy · budget block",
            "project_id": "prj_northwind",
            "policy_id": "pol_locked",
            "brief": "Four landscape campaign variants.",
            "provider": "dara",
            "model": "policy/v1",
            "outcome": "blocked",
            "approved": False,
            "qa_score": None,
            "qa_attempts": 0,
            "cost_usd": "0.000000",
            "saved_cost_usd": "0.120000",
            "asset_url": None,
            "events": [
                event(
                    0,
                    "policy.blocked",
                    "dara",
                    "policy/v1",
                    "Run budget exceeded; no provider was called and $0.120000 was prevented.",
                )
            ],
        },
        {
            "seed_id": "seed_blocked_shape",
            "pipeline_id": "motion-spot",
            "title": "Locked policy · modality block",
            "project_id": "prj_atlas",
            "policy_id": "pol_locked",
            "brief": "A four-second architectural motion spot.",
            "provider": "dara",
            "model": "policy/v1",
            "outcome": "blocked",
            "approved": False,
            "qa_score": None,
            "qa_attempts": 0,
            "cost_usd": "0.000000",
            "saved_cost_usd": "0.430000",
            "asset_url": None,
            "events": [
                event(
                    0,
                    "policy.blocked",
                    "dara",
                    "policy/v1",
                    "Video is not allowed by this policy; no provider was called.",
                )
            ],
        },
        {
            "seed_id": "seed_regeneration",
            "pipeline_id": "regenerate",
            "title": "Manifest regeneration · lineage linked",
            "project_id": "prj_northwind",
            "policy_id": "pol_standard",
            "brief": "Reproduce the recorded editorial still conditions.",
            "provider": "openai",
            "model": "gpt-image-2",
            "outcome": "succeeded",
            "approved": True,
            "qa_score": 0.95,
            "qa_attempts": 1,
            "cost_usd": "0.015000",
            "saved_cost_usd": "0.000000",
            "asset_url": "/dara-verified-sample.png",
            "events": short_events(
                provider="openai",
                model="gpt-image-2",
                pipeline="regenerate",
            ),
        },
        {
            "seed_id": "seed_motion_primary",
            "pipeline_id": "motion-spot",
            "title": "Motion spot fixture · primary route",
            "project_id": "prj_atlas",
            "policy_id": "pol_permissive",
            "brief": "Slow push through a quiet hotel lobby at dusk.",
            "provider": "genblaze-testing",
            "model": "mock-video-v1",
            "outcome": "succeeded",
            "approved": True,
            "qa_score": 0.90,
            "qa_attempts": 1,
            "cost_usd": "0.000000",
            "saved_cost_usd": "0.000000",
            "asset_url": None,
            "events": short_events(
                provider="genblaze-testing",
                model="mock-video-v1",
                pipeline="motion-spot",
            ),
        },
        {
            "seed_id": "seed_motion_fallback",
            "pipeline_id": "motion-spot",
            "title": "Motion spot fixture · fallback recovered",
            "project_id": "prj_atlas",
            "policy_id": "pol_permissive",
            "brief": "Close tracking shot across a brass room key.",
            "provider": "genblaze-testing",
            "model": "mock-video-fallback-v1",
            "outcome": "succeeded",
            "approved": True,
            "qa_score": 0.87,
            "qa_attempts": 1,
            "cost_usd": "0.000000",
            "saved_cost_usd": "0.000000",
            "asset_url": None,
            "events": [
                event(0, "policy.allowed", "dara", "policy/v1", "Pre-flight policy allowed."),
                event(
                    1_100,
                    "step.failover",
                    "genblaze-testing",
                    "mock-video-v1",
                    "Primary fixture route failed; fallback moved to mock-video-fallback-v1.",
                ),
                event(
                    95_000,
                    "run.completed",
                    "dara",
                    "motion-spot",
                    "Fallback video, narration, and composite were sealed.",
                ),
            ],
        },
        {
            "seed_id": "seed_motion_failed",
            "pipeline_id": "motion-spot",
            "title": "Motion spot fixture · failed attempt retained",
            "project_id": "prj_field_notes",
            "policy_id": "pol_permissive",
            "brief": "Macro motion across notebook paper grain.",
            "provider": "genblaze-testing",
            "model": "mock-video-v1",
            "outcome": "failed",
            "approved": False,
            "qa_score": None,
            "qa_attempts": 0,
            "cost_usd": "0.000000",
            "saved_cost_usd": "0.000000",
            "asset_url": None,
            "events": short_events(
                provider="genblaze-testing",
                model="mock-video-v1",
                pipeline="motion-spot",
                outcome="failed",
            ),
        },
    ]
    for index, voice in enumerate(("alloy", "coral", "onyx", "sage"), start=1):
        runs.append(
            {
                "seed_id": f"seed_voice_{voice}",
                "pipeline_id": "voiceover-pack",
                "title": f"Voice pack · {voice}",
                "project_id": "prj_field_notes",
                "policy_id": "pol_standard",
                "brief": "Dara keeps every generation governed and verifiable.",
                "provider": "genblaze-testing",
                "model": "mock-audio-v1",
                "outcome": "succeeded",
                "approved": True,
                "qa_score": None,
                "qa_attempts": 0,
                "cost_usd": "0.000000",
                "saved_cost_usd": "0.000000",
                "asset_url": None,
                "voice": voice,
                "batch_index": index - 1,
                "events": short_events(
                    provider="genblaze-testing",
                    model="mock-audio-v1",
                    pipeline="voiceover-pack",
                ),
            }
        )

    production_proofs = {
        "seed_blocked_budget",
        "seed_blocked_shape",
        "seed_regeneration",
    }
    for run in runs:
        run["evidence"] = (
            "production-proof"
            if run["seed_id"] in production_proofs
            else "deterministic-fixture"
        )

    blocked = [run for run in runs if run["outcome"] == "blocked"]
    revised = [
        run
        for run in runs
        if any(event["type"] == "qa.revised" for event in run["events"])
    ]
    pipelines = {run["pipeline_id"] for run in runs}
    assert 12 <= len(runs) <= 15
    assert len(blocked) >= 2
    assert revised and revised[0]["qa_attempts"] >= 2
    assert {"still-campaign", "motion-spot", "voiceover-pack"} <= pipelines
    return {
        "schema_version": 1,
        "generated_at": GENERATED_AT,
        "default_seed_id": "seed_still_qa_revision",
        "runs": runs,
    }


def main() -> None:
    output = Path(__file__).resolve().parents[2] / "seeds" / "demo-runs.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build_corpus(), indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
