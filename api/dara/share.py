from __future__ import annotations

import hashlib
import json
import re
import secrets
import shutil
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from genblaze_core import EmbedPolicy, Manifest, PromptVisibility
from genblaze_core.media import SmartEmbedder
from pydantic import BaseModel, ConfigDict, Field

from .jobs import LiveRunRecord
from .storage import DaraStorage
from .verify import (
    AssetRef,
    HashIndexPointer,
    TRUST_NOTE,
    asset_ref_key,
    hash_index_key,
    manifest_key,
)


TOKEN_PATTERN = re.compile(r"^shr_[A-Za-z0-9_-]{40,64}$")


class ShareNotFoundError(LookupError):
    pass


class ShareExpiredError(LookupError):
    pass


class ShareIntegrityError(RuntimeError):
    pass


class ShareCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=5, max_length=100)
    asset_ids: tuple[str, ...] = Field(min_length=1, max_length=8)
    expires_in_days: int = Field(default=30, ge=1, le=90)


class ShareRedaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strip_prompt: bool = True
    strip_params: bool = True
    embed_mode: Literal["pointer"] = "pointer"


class SharedAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    shared_sha256: str
    storage_key: str
    pointer_key: str
    mime_type: str
    bytes: int
    provider: str
    model: str
    generated_at: datetime
    source_manifest_hash: str


class ShareRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    token: str
    tenant_id: str
    job_id: str
    created_by_actor_id: str | None = None
    assets: list[SharedAsset]
    redaction: ShareRedaction = Field(default_factory=ShareRedaction)
    created_at: datetime
    expires_at: datetime
    view_count: int = 0


class PublicSharedAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    mime_type: str
    shared_sha256: str
    verification: Literal["record-matched"]
    provider: str
    model: str
    generated_at: datetime


class PublicShare(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    status: Literal["active"] = "active"
    issued_at: datetime
    expires_at: datetime
    view_count: int
    assets: list[PublicSharedAsset]
    redaction: ShareRedaction
    disclosure: str = (
        "Prompt and generation parameters were withheld by the project's "
        "disclosure policy."
    )
    trust_note: str = TRUST_NOTE


def share_key(token: str) -> str:
    return f"dara/state/shares/{token}.json"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ShareService:
    def __init__(self, storage: DaraStorage) -> None:
        self.storage = storage

    def create(
        self,
        run: LiveRunRecord,
        *,
        asset_ids: tuple[str, ...],
        expires_in_days: int,
        actor_id: str | None = None,
    ) -> ShareRecord:
        if run.status != "succeeded" or run.genblaze_run_id is None:
            raise ShareIntegrityError("Only a completed, trusted run can be shared.")
        if len(set(asset_ids)) != len(asset_ids):
            raise ShareIntegrityError("Share asset identifiers must be unique.")
        if run.asset_id is None or set(asset_ids) != {run.asset_id}:
            raise ShareIntegrityError(
                "Every shared asset must belong to the selected completed run."
            )

        manifest = self.storage.get_json(
            manifest_key(run.genblaze_run_id),
            Manifest,
        )
        if manifest is None or not manifest.verify_hash() or not manifest.verify():
            raise ShareIntegrityError(
                "The trusted generation manifest is missing or invalid."
            )

        token = f"shr_{secrets.token_urlsafe(32)}"
        now = datetime.now(UTC)
        shared_assets = [
            self._create_asset(token, asset_id, manifest)
            for asset_id in asset_ids
        ]
        record = ShareRecord(
            token=token,
            tenant_id=run.tenant_id,
            job_id=run.job_id,
            created_by_actor_id=actor_id,
            assets=shared_assets,
            created_at=now,
            expires_at=now + timedelta(days=expires_in_days),
        )
        self.storage.put_json(share_key(token), record)
        return record

    def read_public(self, token: str) -> PublicShare:
        if not TOKEN_PATTERN.fullmatch(token):
            raise ShareNotFoundError("Share not found.")
        record = self.storage.get_json(share_key(token), ShareRecord)
        if record is None:
            raise ShareNotFoundError("Share not found.")
        if record.expires_at <= datetime.now(UTC):
            raise ShareExpiredError("This share link has expired.")

        assets: list[PublicSharedAsset] = []
        for asset in record.assets:
            shared_bytes = self.storage.get_bytes(asset.storage_key)
            if shared_bytes is None or _sha256(shared_bytes) != asset.shared_sha256:
                raise ShareIntegrityError(
                    "The token-scoped shared file no longer matches its trusted record."
                )
            assets.append(
                PublicSharedAsset(
                    url=self.storage.presign(asset.storage_key, expires_in=900),
                    mime_type=asset.mime_type,
                    shared_sha256=asset.shared_sha256,
                    verification="record-matched",
                    provider=asset.provider,
                    model=asset.model,
                    generated_at=asset.generated_at,
                )
            )

        record.view_count += 1
        self.storage.put_json(share_key(token), record)
        return PublicShare(
            issued_at=record.created_at,
            expires_at=record.expires_at,
            view_count=record.view_count,
            assets=assets,
            redaction=record.redaction,
        )

    def _create_asset(
        self,
        token: str,
        asset_id: str,
        manifest: Manifest,
    ) -> SharedAsset:
        reference = self.storage.get_json(asset_ref_key(asset_id), AssetRef)
        if (
            reference is None
            or reference.run_id != manifest.run.run_id
            or not reference.approved
        ):
            raise ShareIntegrityError("The requested asset is not an approved run output.")
        source_bytes = self.storage.get_bytes(reference.source_content_address)
        if source_bytes is None or _sha256(source_bytes) != reference.source_sha256:
            raise ShareIntegrityError(
                "The trusted source bytes are missing or do not match their record."
            )

        step = next(
            (
                step
                for step in manifest.run.steps
                if any(asset.asset_id == asset_id for asset in step.assets)
            ),
            None,
        )
        if step is None:
            raise ShareIntegrityError(
                "The requested asset is not declared by the trusted manifest."
            )

        extension = Path(reference.source_content_address).suffix.lower() or ".bin"
        storage_key = f"dara/share-assets/{token}/{asset_id}{extension}"
        pointer_key = f"{storage_key}.genblaze.json"
        pointer_manifest = manifest.model_copy(deep=True)
        pointer_manifest.manifest_uri = f"dara://share/{token}/trusted-manifest"
        embed_policy = EmbedPolicy(
            prompt_visibility=PromptVisibility.PRIVATE,
            embed_mode="pointer",
            include_params=False,
            include_seed=False,
        )
        with tempfile.TemporaryDirectory(prefix="dara-share-") as temporary:
            source_path = Path(temporary) / f"source{extension}"
            shared_path = Path(temporary) / f"shared{extension}"
            source_path.write_bytes(source_bytes)
            shutil.copyfile(source_path, shared_path)
            embedded = SmartEmbedder().embed(
                source_path,
                pointer_manifest,
                shared_path,
                policy=embed_policy,
                mime_type=reference.mime_type,
            )
            if embedded.method != "pointer" or embedded.sidecar_path is None:
                raise ShareIntegrityError(
                    "Genblaze did not produce the required redacted pointer manifest."
                )
            shared_bytes = shared_path.read_bytes()
            pointer_bytes = embedded.sidecar_path.read_bytes()

        pointer_payload = json.loads(pointer_bytes)
        if set(pointer_payload) != {
            "schema_version",
            "canonical_hash",
            "manifest_uri",
        }:
            raise ShareIntegrityError(
                "The redacted pointer contains fields outside the disclosure policy."
            )
        if pointer_payload["canonical_hash"] != manifest.canonical_hash:
            raise ShareIntegrityError(
                "The redacted pointer no longer binds to the trusted manifest."
            )
        shared_sha256 = _sha256(shared_bytes)
        self.storage.put_bytes(
            storage_key,
            shared_bytes,
            content_type=reference.mime_type,
            metadata={"sha256": shared_sha256, "share-token": token},
        )
        self.storage.put_bytes(
            pointer_key,
            pointer_bytes,
            content_type="application/json",
            metadata={
                "manifest-hash": manifest.canonical_hash,
                "share-token": token,
            },
        )
        self.storage.put_json(
            hash_index_key(shared_sha256),
            HashIndexPointer(
                sha256=shared_sha256,
                asset_id=asset_id,
                run_id=manifest.run.run_id,
                hash_kind="shared",
            ),
        )
        return SharedAsset(
            asset_id=asset_id,
            shared_sha256=shared_sha256,
            storage_key=storage_key,
            pointer_key=pointer_key,
            mime_type=reference.mime_type,
            bytes=len(shared_bytes),
            provider=step.provider or "unknown",
            model=step.model,
            generated_at=manifest.run.created_at,
            source_manifest_hash=manifest.canonical_hash,
        )
