from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Literal

from genblaze_core import Manifest
from genblaze_core.exceptions import EmbeddingError
from genblaze_core.media import get_handler, guess_mime
from pydantic import BaseModel, ConfigDict, Field

from .storage import DaraStorage, StorageUnavailableError


TRUST_NOTE = (
    "Tamper-evident within the issuing organisation's storage. "
    "Not an adversarial authenticity proof."
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class UnsupportedMediaError(ValueError):
    pass


class InvalidHashError(ValueError):
    pass


class AssetRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    asset_id: str
    run_id: str
    source_sha256: str
    published_sha256: str | None = None
    mime_type: str
    bytes: int
    source_content_address: str
    published_content_address: str | None = None
    modality: str
    manifest_embedded: bool = False
    redacted: bool = False
    qa_score: float | None = None
    approved: bool = False
    cost_usd: str = "0.000000"
    cost_basis: Literal["known", "estimated", "unknown"] = "unknown"


class HashIndexPointer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    sha256: str
    asset_id: str
    run_id: str
    hash_kind: Literal["source", "published", "shared"]


class VerifyStep(BaseModel):
    provider: str | None
    model: str
    modality: str
    prompt: str | None
    params: dict[str, object]
    cost_usd: str | None


class VerifyManifest(BaseModel):
    canonical_hash: str
    hash_matches: bool
    declared_hashes_match: bool
    run_id: str
    created_at: str
    steps: list[VerifyStep]
    parent_run_id: str | None
    redacted: bool = False


class LineageItem(BaseModel):
    run_id: str
    at: str
    relationship: Literal["generated", "parent"]
    provider: str | None = None
    model: str | None = None


class VerificationResponse(BaseModel):
    result: Literal["embedded", "matched-by-hash", "unknown"]
    verification: Literal[
        "trusted-match", "trusted-mismatch", "self-consistent", "unknown"
    ]
    storage_status: Literal["available", "unavailable"]
    verified: bool
    uploaded_sha256: str
    expected_published_sha256: str | None = None
    manifest: VerifyManifest | None = None
    lineage: list[LineageItem] = Field(default_factory=list)
    warning: str | None = None
    trust_note: str = TRUST_NOTE


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def asset_ref_key(asset_id: str) -> str:
    return f"dara/state/assets/{asset_id}.json"


def hash_index_key(sha256: str) -> str:
    return f"dara/index/sha/{sha256}.json"


def manifest_key(run_id: str) -> str:
    return f"dara/manifests/{run_id}.json"


def _manifest_summary(manifest: Manifest) -> VerifyManifest:
    steps = [
        VerifyStep(
            provider=step.provider,
            model=step.model,
            modality=step.modality.value,
            prompt=step.prompt,
            params=step.params,
            cost_usd=f"{step.cost_usd:.6f}" if step.cost_usd is not None else None,
        )
        for step in manifest.run.steps
    ]
    return VerifyManifest(
        canonical_hash=manifest.canonical_hash,
        hash_matches=manifest.verify_hash(),
        declared_hashes_match=manifest.verify(),
        run_id=manifest.run.run_id,
        created_at=manifest.run.created_at.isoformat().replace("+00:00", "Z"),
        steps=steps,
        parent_run_id=manifest.run.parent_run_id,
    )


def _lineage(manifest: Manifest) -> list[LineageItem]:
    items = [
        LineageItem(
            run_id=manifest.run.run_id,
            at=manifest.run.created_at.isoformat().replace("+00:00", "Z"),
            relationship="generated",
            provider=step.provider,
            model=step.model,
        )
        for step in manifest.run.steps
    ]
    if manifest.run.parent_run_id:
        items.insert(
            0,
            LineageItem(
                run_id=manifest.run.parent_run_id,
                at=manifest.run.created_at.isoformat().replace("+00:00", "Z"),
                relationship="parent",
            ),
        )
    return items


class Verifier:
    def __init__(self, storage: DaraStorage) -> None:
        self.storage = storage

    def verify_path(self, path: Path) -> VerificationResponse:
        uploaded_sha256 = sha256_file(path)
        manifest = self._extract_manifest(path)
        if manifest is None:
            return self.lookup_hash(uploaded_sha256)
        summary = _manifest_summary(manifest)
        lineage = _lineage(manifest)
        if not summary.hash_matches or not summary.declared_hashes_match:
            return VerificationResponse(
                result="embedded",
                verification="unknown",
                storage_status="available",
                verified=False,
                uploaded_sha256=uploaded_sha256,
                manifest=summary,
                lineage=lineage,
                warning="The embedded manifest did not pass its internal integrity checks.",
            )

        try:
            trusted_manifest = self.storage.get_json(
                manifest_key(manifest.run.run_id),
                Manifest,
            )
            asset_refs = self._trusted_asset_refs(manifest)
        except StorageUnavailableError:
            return VerificationResponse(
                result="embedded",
                verification="self-consistent",
                storage_status="unavailable",
                verified=False,
                uploaded_sha256=uploaded_sha256,
                manifest=summary,
                lineage=lineage,
                warning="Trusted storage is temporarily unavailable. Retry verification.",
            )

        manifest_is_trusted = (
            trusted_manifest is not None
            and trusted_manifest.canonical_hash == manifest.canonical_hash
        )
        if not manifest_is_trusted or not asset_refs:
            return VerificationResponse(
                result="embedded",
                verification="self-consistent",
                storage_status="available",
                verified=False,
                uploaded_sha256=uploaded_sha256,
                manifest=summary,
                lineage=lineage,
                warning="The manifest is internally consistent but has no trusted Dara record.",
            )

        matched = next(
            (
                ref
                for ref in asset_refs
                if ref.published_sha256 == uploaded_sha256 and ref.approved
            ),
            None,
        )
        reference = matched or asset_refs[0]
        expected = reference.published_sha256
        is_match = matched is not None and expected is not None
        return VerificationResponse(
            result="embedded",
            verification="trusted-match" if is_match else "trusted-mismatch",
            storage_status="available",
            verified=is_match,
            uploaded_sha256=uploaded_sha256,
            expected_published_sha256=expected,
            manifest=summary,
            lineage=lineage,
            warning=(
                None
                if is_match
                else "The embedded record is trusted, but the uploaded bytes have changed."
            ),
        )

    def lookup_hash(self, sha256: str) -> VerificationResponse:
        normalized = sha256.lower()
        if not SHA256_PATTERN.fullmatch(normalized):
            raise InvalidHashError("SHA-256 must be exactly 64 hexadecimal characters.")
        pointer = self.storage.get_json(
            hash_index_key(normalized),
            HashIndexPointer,
        )
        if pointer is None:
            return VerificationResponse(
                result="unknown",
                verification="unknown",
                storage_status="available",
                verified=False,
                uploaded_sha256=normalized,
                warning=(
                    "No record of this file. It may have been generated elsewhere, "
                    "or modified after generation."
                ),
            )
        asset_ref = self.storage.get_json(asset_ref_key(pointer.asset_id), AssetRef)
        manifest = self.storage.get_json(manifest_key(pointer.run_id), Manifest)
        if asset_ref is None or manifest is None:
            return VerificationResponse(
                result="unknown",
                verification="unknown",
                storage_status="available",
                verified=False,
                uploaded_sha256=normalized,
                warning="The hash index exists, but its trusted record is incomplete.",
            )
        expected = asset_ref.published_sha256
        is_published_match = (
            pointer.hash_kind == "published"
            and expected == normalized
            and asset_ref.approved
        )
        return VerificationResponse(
            result="matched-by-hash",
            verification="trusted-match" if is_published_match else "self-consistent",
            storage_status="available",
            verified=is_published_match,
            uploaded_sha256=normalized,
            expected_published_sha256=expected,
            manifest=_manifest_summary(manifest),
            lineage=_lineage(manifest),
            warning=(
                "Matched by whole-file hash; no embedded manifest was found."
                if is_published_match
                else "Matched a trusted source record; this is not a published-file match."
            ),
        )

    def _extract_manifest(self, path: Path) -> Manifest | None:
        mime_type = guess_mime(path)
        handler = get_handler(mime_type)
        if handler is None:
            raise UnsupportedMediaError(
                f"Dara cannot inspect files of type {mime_type}."
            )
        try:
            return handler.extract(path)
        except EmbeddingError as exc:
            if "no genblaze manifest found" in str(exc).lower():
                return None
            raise UnsupportedMediaError(
                "Dara found unreadable provenance metadata in this file."
            ) from exc

    def _trusted_asset_refs(self, manifest: Manifest) -> list[AssetRef]:
        refs: list[AssetRef] = []
        for step in manifest.run.steps:
            for asset in step.assets:
                ref = self.storage.get_json(asset_ref_key(asset.asset_id), AssetRef)
                if ref is not None and ref.run_id == manifest.run.run_id:
                    refs.append(ref)
        return refs
