from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from genblaze_core import Manifest
from genblaze_core.media import SmartEmbedder

from dara.storage import DaraStorage
from dara.verify import (
    AssetRef,
    HashIndexPointer,
    asset_ref_key,
    hash_index_key,
    manifest_key,
)


DEFAULT_RUN_ID = "f1a3332d-5727-4644-976a-2f7c09c74e82"
DEFAULT_RUN_PREFIX = f"dara/live/runs/demo/2026-07-29/{DEFAULT_RUN_ID}"


def content_address(kind: str, sha256: str, extension: str) -> str:
    return f"dara/{kind}/{sha256[:2]}/{sha256[2:4]}/{sha256}{extension}"


def publish_spike() -> dict[str, object]:
    project_root = Path(__file__).resolve().parents[3]
    load_dotenv(project_root / ".env")
    storage = DaraStorage.from_env()

    run_id = os.getenv("DARA_PUBLISH_RUN_ID", DEFAULT_RUN_ID)
    run_prefix = os.getenv("DARA_PUBLISH_RUN_PREFIX", DEFAULT_RUN_PREFIX)
    keys = storage.list_prefix(run_prefix)
    source_key = next(key for key in keys if "/assets/" in key)
    run_manifest_key = next(key for key in keys if key.endswith("/manifest.json"))
    source_bytes = storage.get_bytes(source_key)
    manifest_bytes = storage.get_bytes(run_manifest_key)
    if source_bytes is None or manifest_bytes is None:
        raise RuntimeError("The spike source asset or manifest is missing.")

    manifest = Manifest.model_validate_json(manifest_bytes)
    if manifest.run.run_id != run_id:
        raise RuntimeError("The selected run prefix contains a different manifest.")
    extension = Path(source_key).suffix.lower()
    mime_type = manifest.run.steps[0].assets[0].media_type
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    source_asset = next(
        asset
        for step in manifest.run.steps
        for asset in step.assets
        if asset.sha256 == source_sha256
    )

    with tempfile.TemporaryDirectory(prefix="dara-publish-") as temporary:
        source_path = Path(temporary) / f"source{extension}"
        published_path = Path(temporary) / f"published{extension}"
        source_path.write_bytes(source_bytes)
        embed_result = SmartEmbedder().embed(
            source_path,
            manifest,
            published_path,
            mime_type=mime_type,
        )
        if embed_result.method != "inline":
            raise RuntimeError(
                f"Expected inline manifest embedding, got {embed_result.method}."
            )
        published_bytes = published_path.read_bytes()

    published_sha256 = hashlib.sha256(published_bytes).hexdigest()
    source_content_address = content_address("assets", source_sha256, extension)
    published_content_address = content_address(
        "published",
        published_sha256,
        extension,
    )
    storage.put_bytes(
        source_content_address,
        source_bytes,
        content_type=mime_type,
        metadata={"sha256": source_sha256, "run-id": run_id},
    )
    storage.put_bytes(
        published_content_address,
        published_bytes,
        content_type=mime_type,
        metadata={"sha256": published_sha256, "run-id": run_id},
    )
    storage.put_json(manifest_key(run_id), manifest)

    step = manifest.run.steps[0]
    asset_ref = AssetRef(
        asset_id=source_asset.asset_id,
        run_id=run_id,
        source_sha256=source_sha256,
        published_sha256=published_sha256,
        mime_type=mime_type,
        bytes=len(published_bytes),
        source_content_address=source_content_address,
        published_content_address=published_content_address,
        modality=step.modality.value,
        manifest_embedded=True,
        approved=True,
        cost_usd=f"{step.cost_usd:.6f}" if step.cost_usd is not None else "0.000000",
        cost_basis="known" if step.cost_usd is not None else "unknown",
    )
    storage.put_json(asset_ref_key(source_asset.asset_id), asset_ref)
    for sha256, hash_kind in (
        (source_sha256, "source"),
        (published_sha256, "published"),
    ):
        storage.put_json(
            hash_index_key(sha256),
            HashIndexPointer(
                sha256=sha256,
                asset_id=source_asset.asset_id,
                run_id=run_id,
                hash_kind=hash_kind,
            ),
        )

    output_path = project_root.parent / "outputs" / "dara-verified-published.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(published_bytes)
    verification = storage.get_json(
        hash_index_key(published_sha256),
        HashIndexPointer,
    )
    return {
        "run_id": run_id,
        "asset_id": source_asset.asset_id,
        "source_sha256": source_sha256,
        "published_sha256": published_sha256,
        "manifest_hash": manifest.canonical_hash,
        "manifest_embedded": True,
        "published_index_written": verification is not None,
        "source_content_address": source_content_address,
        "published_content_address": published_content_address,
        "preview_path": str(output_path),
    }


def main() -> None:
    print(json.dumps(publish_spike(), indent=2))


if __name__ == "__main__":
    main()
