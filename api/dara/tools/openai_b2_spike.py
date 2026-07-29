from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from genblaze_core import KeyStrategy, Modality, ObjectStorageSink, Pipeline
from genblaze_openai import DalleProvider
from genblaze_s3 import S3StorageBackend

from dara.tools.b2_spike import without_query


DEFAULT_MODEL = "gpt-image-2"
DEFAULT_PROMPT = """
Create a cinematic square product visual for Dara, an AI media control system.
Show a dark obsidian command center with one luminous electric-blue provenance
thread connecting an image frame, an audio waveform, and a video frame. Use
precise editorial lighting, restrained cobalt accents, subtle glass surfaces,
and premium enterprise software art direction. No logos, no words, no letters,
no watermarks, no people.
""".strip()


def run_openai_b2_spike() -> dict[str, object]:
    project_root = Path(__file__).resolve().parents[3]
    load_dotenv(project_root / ".env")

    required = (
        "OPENAI_API_KEY",
        "B2_KEY_ID",
        "B2_APP_KEY",
        "B2_BUCKET",
        "B2_REGION",
    )
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing required configuration: {', '.join(missing)}")

    model = os.getenv("DARA_OPENAI_IMAGE_MODEL", DEFAULT_MODEL)
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
    )

    with tempfile.TemporaryDirectory(prefix="dara-openai-") as output_dir:
        provider = DalleProvider(output_dir=output_dir, http_timeout=180.0)
        result = (
            Pipeline("dara-openai-image", tenant_id="demo", project_id="dara")
            .step(
                provider,
                model=model,
                prompt=DEFAULT_PROMPT,
                modality=Modality.IMAGE,
                size="1024x1024",
                quality="low",
                output_format="png",
                n=1,
            )
            .run(sink=sink, timeout=240.0, raise_on_failure=True)
        )

    step = result.run.steps[0]
    asset = step.assets[0]
    duration_seconds = None
    if step.started_at and step.completed_at:
        duration_seconds = (step.completed_at - step.started_at).total_seconds()
    return {
        "provider": step.provider,
        "model": step.model,
        "bucket": os.environ["B2_BUCKET"],
        "region": os.environ["B2_REGION"],
        "run_id": result.run.run_id,
        "asset_id": asset.asset_id,
        "asset_url": without_query(asset.url),
        "asset_sha256": asset.sha256,
        "manifest_uri": without_query(result.manifest.manifest_uri),
        "canonical_hash": result.manifest.canonical_hash,
        "verify_hash": result.manifest.verify_hash(),
        "verify": result.manifest.verify(),
        "cost_usd": step.cost_usd,
        "duration_seconds": duration_seconds,
    }


def main() -> None:
    print(json.dumps(run_openai_b2_spike(), indent=2))


if __name__ == "__main__":
    main()
