from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from genblaze_core import Asset, KeyStrategy, Modality, ObjectStorageSink, Pipeline
from genblaze_core.testing import MockProvider
from genblaze_s3 import S3StorageBackend


def without_query(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def run_b2_spike() -> dict[str, object]:
    project_root = Path(__file__).resolve().parents[3]
    load_dotenv(project_root / ".env")

    required = ("B2_KEY_ID", "B2_APP_KEY", "B2_BUCKET", "B2_REGION")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing required B2 configuration: {', '.join(missing)}")

    backend = S3StorageBackend.for_backblaze(
        os.environ["B2_BUCKET"],
        region=os.environ["B2_REGION"],
        key_id=os.environ["B2_KEY_ID"],
        app_key=os.environ["B2_APP_KEY"],
        preflight=True,
    )
    sink = ObjectStorageSink(
        backend,
        prefix="dara/spikes",
        key_strategy=KeyStrategy.HIERARCHICAL,
    )
    source = project_root / "public" / "og.png"
    with tempfile.TemporaryDirectory(prefix="dara-b2-spike-") as staging_dir:
        staged_source = Path(staging_dir) / "dara-social-card.png"
        shutil.copy2(source, staged_source)
        provider = MockProvider(
            name="dara-local-spike",
            assets=[Asset(url=staged_source.as_uri(), media_type="image/png")],
            cost_usd=0.0,
        )
        result = (
            Pipeline("dara-b2-spike", tenant_id="demo", project_id="dara")
            .step(
                provider,
                model="local-social-card-v1",
                prompt="Dara social preview card used for the B2 storage spike",
                modality=Modality.IMAGE,
            )
            .run(sink=sink, raise_on_failure=True)
        )
    asset = result.run.steps[0].assets[0]
    return {
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
    }


def main() -> None:
    print(json.dumps(run_b2_spike(), indent=2))


if __name__ == "__main__":
    main()
