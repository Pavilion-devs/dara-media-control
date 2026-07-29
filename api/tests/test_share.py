from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
import unittest
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from genblaze_core import Asset, Modality, Pipeline
from genblaze_core.testing import MockProvider
from PIL import Image

import dara.main as main_module
from dara.jobs import LiveRunRecord, MemoryLiveRunStore
from dara.main import app, get_share_service
from dara.share import ShareExpiredError, ShareService, share_key
from dara.storage import DaraStorage
from dara.verify import AssetRef, asset_ref_key, manifest_key


@dataclass(frozen=True)
class MemoryEntry:
    key: str


class MemoryBackend:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key, data, *, content_type=None, metadata=None):
        del content_type, metadata
        self.objects[key] = bytes(data)
        return f"memory://{key}"

    def get(self, key):
        return self.objects[key]

    def exists(self, key):
        return key in self.objects

    def list(self, prefix="", *, max_keys=1000, continuation_token=None):
        del continuation_token
        entries = [
            MemoryEntry(key)
            for key in sorted(self.objects)
            if key.startswith(prefix)
        ][:max_keys]
        return SimpleNamespace(entries=entries, next_token=None)

    def get_url(self, key, *, expires_in=3600):
        return f"memory://{key}?expires={expires_in}"


class ShareServiceTests(unittest.TestCase):
    def fixture(self, directory: Path):
        source_path = directory / "source.png"
        Image.new("RGB", (24, 24), color=(20, 54, 86)).save(source_path, "PNG")
        source_bytes = source_path.read_bytes()
        source_sha256 = hashlib.sha256(source_bytes).hexdigest()
        asset = Asset(
            url=source_path.as_uri(),
            media_type="image/png",
            sha256=source_sha256,
            size_bytes=len(source_bytes),
        )
        result = (
            Pipeline("share-fixture", tenant_id="demo", project_id="prj_share")
            .step(
                MockProvider(name="openai", assets=[asset]),
                model="gpt-image-2",
                prompt="A private client campaign subject",
                modality=Modality.IMAGE,
                seed=431,
                confidential_parameter="must-not-leak",
            )
            .run(raise_on_failure=True)
        )
        stored_asset = result.run.steps[0].assets[0]
        backend = MemoryBackend()
        storage = DaraStorage(backend)
        source_key = f"dara/assets/{source_sha256}.png"
        storage.put_bytes(source_key, source_bytes, content_type="image/png")
        storage.put_json(manifest_key(result.run.run_id), result.manifest)
        storage.put_json(
            asset_ref_key(stored_asset.asset_id),
            AssetRef(
                asset_id=stored_asset.asset_id,
                run_id=result.run.run_id,
                source_sha256=source_sha256,
                mime_type="image/png",
                bytes=len(source_bytes),
                source_content_address=source_key,
                modality="image",
                approved=True,
            ),
        )
        run = LiveRunRecord(
            job_id="job_share_test",
            project_id="prj_share",
            status="succeeded",
            prompt="A private client campaign subject",
            aspect_ratio="1:1",
            policy_id="pol_standard",
            expected_cost_usd=Decimal("0.020000"),
            worst_case_cost_usd=Decimal("0.060000"),
            genblaze_run_id=result.run.run_id,
            asset_id=stored_asset.asset_id,
            source_sha256=source_sha256,
        )
        return ShareService(storage), storage, backend, run

    def test_share_uses_redacted_pointer_and_verifies_served_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service, storage, backend, run = self.fixture(Path(temporary))
            record = service.create(
                run,
                asset_ids=(run.asset_id,),
                expires_in_days=30,
            )
            pointer = json.loads(backend.objects[record.assets[0].pointer_key])
            public = service.read_public(record.token)

        self.assertEqual(
            set(pointer),
            {"schema_version", "canonical_hash", "manifest_uri"},
        )
        self.assertNotIn("prompt", json.dumps(pointer))
        self.assertNotIn("params", json.dumps(pointer))
        self.assertEqual(pointer["canonical_hash"], record.assets[0].source_manifest_hash)
        self.assertEqual(public.assets[0].verification, "record-matched")
        self.assertEqual(public.assets[0].shared_sha256, record.assets[0].shared_sha256)
        self.assertEqual(public.view_count, 1)
        persisted = storage.get_json(share_key(record.token), type(record))
        self.assertEqual(persisted and persisted.view_count, 1)

    def test_expired_share_is_not_served(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service, storage, _, run = self.fixture(Path(temporary))
            record = service.create(
                run,
                asset_ids=(run.asset_id,),
                expires_in_days=1,
            )
            record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            storage.put_json(share_key(record.token), record)
            with self.assertRaises(ShareExpiredError):
                service.read_public(record.token)

    def test_authenticated_create_and_public_read_never_return_private_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service, _, _, run = self.fixture(Path(temporary))
            run_store = MemoryLiveRunStore()
            asyncio.run(run_store.put(run))
            app.dependency_overrides[get_share_service] = lambda: service
            try:
                with (
                    patch.object(main_module, "live_run_store", run_store),
                    patch.dict(
                        "os.environ",
                        {"DARA_API_TOKEN": "share-test-token"},
                    ),
                    TestClient(app) as client,
                ):
                    created = client.post(
                        "/v1/shares",
                        headers={"Authorization": "Bearer share-test-token"},
                        json={
                            "job_id": run.job_id,
                            "asset_ids": [run.asset_id],
                            "expires_in_days": 7,
                        },
                    )
                    public = client.get(
                        f"/v1/share/{created.json()['token']}"
                    )
            finally:
                app.dependency_overrides.clear()

        self.assertEqual(created.status_code, 201)
        self.assertEqual(public.status_code, 200)
        payload = public.json()
        serialized = json.dumps(payload)
        self.assertNotIn(run.job_id, serialized)
        self.assertNotIn(run.genblaze_run_id, serialized)
        self.assertNotIn(run.prompt, serialized)
        self.assertNotIn("params", payload)
        self.assertNotIn("must-not-leak", serialized)
        self.assertEqual(payload["assets"][0]["verification"], "record-matched")


if __name__ == "__main__":
    unittest.main()
