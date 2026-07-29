from __future__ import annotations

import hashlib
import struct
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from genblaze_core import Asset, Modality, Pipeline
from genblaze_core.media import SmartEmbedder
from genblaze_core.testing import MockProvider
from PIL import Image

from dara.main import app, get_verifier
from dara.storage import DaraStorage
from dara.verify import (
    AssetRef,
    HashIndexPointer,
    Verifier,
    asset_ref_key,
    hash_index_key,
    manifest_key,
)


@dataclass(frozen=True)
class MemoryEntry:
    key: str


class MemoryBackend:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        del content_type, metadata
        self.objects[key] = bytes(data)
        return f"memory://{key}"

    def get(self, key: str) -> bytes:
        return self.objects[key]

    def exists(self, key: str) -> bool:
        return key in self.objects

    def list(
        self,
        prefix: str = "",
        *,
        max_keys: int = 1000,
        continuation_token: str | None = None,
    ) -> SimpleNamespace:
        del continuation_token
        entries = [
            MemoryEntry(key)
            for key in sorted(self.objects)
            if key.startswith(prefix)
        ][:max_keys]
        return SimpleNamespace(entries=tuple(entries), next_token=None)

    def get_url(self, key: str, *, expires_in: int = 3600) -> str:
        return f"memory://{key}?expires={expires_in}"


@dataclass
class VerifyFixture:
    verifier: Verifier
    source_path: Path
    published_path: Path
    source_sha256: str
    published_sha256: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_fixture(directory: Path, *, persist_trusted: bool = True) -> VerifyFixture:
    source_path = directory / "source.png"
    Image.new("RGB", (32, 32), color=(24, 52, 74)).save(source_path, "PNG")
    source_bytes = source_path.read_bytes()
    source_sha256 = sha256_bytes(source_bytes)
    source_asset = Asset(
        url=source_path.as_uri(),
        media_type="image/png",
        sha256=source_sha256,
        size_bytes=len(source_bytes),
    )
    result = (
        Pipeline("verify-fixture", tenant_id="demo", project_id="tests")
        .step(
            MockProvider(name="fixture-provider", assets=[source_asset]),
            model="fixture-image-v1",
            prompt="A deterministic verification fixture",
            modality=Modality.IMAGE,
        )
        .run(raise_on_failure=True)
    )
    published_path = directory / "published.png"
    SmartEmbedder().embed(
        source_path,
        result.manifest,
        published_path,
        mime_type="image/png",
    )
    published_bytes = published_path.read_bytes()
    published_sha256 = sha256_bytes(published_bytes)
    stored_asset = result.run.steps[0].assets[0]
    backend = MemoryBackend()
    storage = DaraStorage(backend)

    if persist_trusted:
        asset_ref = AssetRef(
            asset_id=stored_asset.asset_id,
            run_id=result.run.run_id,
            source_sha256=source_sha256,
            published_sha256=published_sha256,
            mime_type="image/png",
            bytes=len(published_bytes),
            source_content_address=f"assets/{source_sha256}.png",
            published_content_address=f"published/{published_sha256}.png",
            modality="image",
            manifest_embedded=True,
            approved=True,
        )
        storage.put_json(manifest_key(result.run.run_id), result.manifest)
        storage.put_json(asset_ref_key(stored_asset.asset_id), asset_ref)
        storage.put_json(
            hash_index_key(source_sha256),
            HashIndexPointer(
                sha256=source_sha256,
                asset_id=stored_asset.asset_id,
                run_id=result.run.run_id,
                hash_kind="source",
            ),
        )
        storage.put_json(
            hash_index_key(published_sha256),
            HashIndexPointer(
                sha256=published_sha256,
                asset_id=stored_asset.asset_id,
                run_id=result.run.run_id,
                hash_kind="published",
            ),
        )

    return VerifyFixture(
        verifier=Verifier(storage),
        source_path=source_path,
        published_path=published_path,
        source_sha256=source_sha256,
        published_sha256=published_sha256,
    )


def tamper_png(path: Path, output: Path) -> None:
    data = bytearray(path.read_bytes())
    position = 8
    while position < len(data):
        length = struct.unpack(">I", data[position : position + 4])[0]
        chunk_type = bytes(data[position + 4 : position + 8])
        if chunk_type == b"IDAT" and length:
            data[position + 8] ^= 0x01
            output.write_bytes(data)
            return
        position += 12 + length
    raise AssertionError("PNG fixture has no IDAT chunk")


class VerifierTests(unittest.TestCase):
    def test_embedded_published_file_is_a_trusted_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = create_fixture(Path(temporary))
            response = fixture.verifier.verify_path(fixture.published_path)
        self.assertEqual(response.result, "embedded")
        self.assertEqual(response.verification, "trusted-match")
        self.assertTrue(response.verified)
        self.assertEqual(response.uploaded_sha256, fixture.published_sha256)
        self.assertTrue(response.manifest and response.manifest.hash_matches)

    def test_changed_embedded_file_is_a_trusted_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = create_fixture(root)
            tampered = root / "tampered.png"
            tamper_png(fixture.published_path, tampered)
            response = fixture.verifier.verify_path(tampered)
        self.assertEqual(response.verification, "trusted-mismatch")
        self.assertFalse(response.verified)
        self.assertEqual(
            response.expected_published_sha256,
            fixture.published_sha256,
        )
        self.assertNotEqual(response.uploaded_sha256, fixture.published_sha256)

    def test_valid_foreign_manifest_is_only_self_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = create_fixture(Path(temporary), persist_trusted=False)
            response = fixture.verifier.verify_path(fixture.published_path)
        self.assertEqual(response.verification, "self-consistent")
        self.assertFalse(response.verified)

    def test_file_without_manifest_can_match_trusted_source_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = create_fixture(Path(temporary))
            response = fixture.verifier.verify_path(fixture.source_path)
        self.assertEqual(response.result, "matched-by-hash")
        self.assertEqual(response.verification, "self-consistent")
        self.assertFalse(response.verified)


class VerifyEndpointTests(unittest.TestCase):
    def test_upload_endpoint_returns_typed_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = create_fixture(Path(temporary))
            app.dependency_overrides[get_verifier] = lambda: fixture.verifier
            try:
                with TestClient(app) as client:
                    response = client.post(
                        "/v1/verify",
                        files={
                            "file": (
                                "published.png",
                                fixture.published_path.read_bytes(),
                                "image/png",
                            )
                        },
                    )
            finally:
                app.dependency_overrides.clear()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["verification"], "trusted-match")
        self.assertTrue(response.headers["X-Request-Id"].startswith("req_"))

    def test_hash_endpoint_rejects_malformed_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = create_fixture(Path(temporary))
            app.dependency_overrides[get_verifier] = lambda: fixture.verifier
            try:
                with TestClient(app) as client:
                    response = client.get("/v1/verify/not-a-hash")
            finally:
                app.dependency_overrides.clear()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INVALID_REQUEST")


if __name__ == "__main__":
    unittest.main()
