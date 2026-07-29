from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any, Protocol, TypeVar

from genblaze_s3 import S3StorageBackend
from pydantic import BaseModel


class StorageUnavailableError(RuntimeError):
    """The trusted storage service could not complete an operation."""


class StorageBackend(Protocol):
    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def list(
        self,
        prefix: str = "",
        *,
        max_keys: int = 1000,
        continuation_token: str | None = None,
    ) -> Any: ...

    def get_url(self, key: str, *, expires_in: int = 3600) -> str: ...


ModelT = TypeVar("ModelT", bound=BaseModel)


class DaraStorage:
    """Typed object helpers for Dara's only persistence layer."""

    def __init__(self, backend: StorageBackend) -> None:
        self._backend = backend

    @classmethod
    def from_env(cls) -> DaraStorage:
        required = ("B2_KEY_ID", "B2_APP_KEY", "B2_BUCKET", "B2_REGION")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise StorageUnavailableError(
                f"Missing B2 configuration: {', '.join(missing)}"
            )
        backend = S3StorageBackend.for_backblaze(
            os.environ["B2_BUCKET"],
            region=os.environ["B2_REGION"],
            key_id=os.environ["B2_KEY_ID"],
            app_key=os.environ["B2_APP_KEY"],
            public_url_base=os.getenv("B2_PUBLIC_URL_BASE") or None,
            preflight=True,
        )
        return cls(backend)

    def put_json(
        self,
        key: str,
        value: BaseModel | Mapping[str, object],
        *,
        metadata: dict[str, str] | None = None,
    ) -> str:
        if isinstance(value, BaseModel):
            payload = value.model_dump(mode="json")
        else:
            payload = dict(value)
        data = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return self.put_bytes(
            key,
            data,
            content_type="application/json",
            metadata=metadata,
        )

    def get_json(self, key: str, model: type[ModelT]) -> ModelT | None:
        try:
            if not self._backend.exists(key):
                return None
            return model.model_validate_json(self._backend.get(key))
        except StorageUnavailableError:
            raise
        except Exception as exc:
            raise StorageUnavailableError(f"Unable to read trusted object {key}") from exc

    def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        try:
            return self._backend.put(
                key,
                data,
                content_type=content_type,
                metadata=metadata,
            )
        except Exception as exc:
            raise StorageUnavailableError(f"Unable to write trusted object {key}") from exc

    def get_bytes(self, key: str) -> bytes | None:
        try:
            if not self._backend.exists(key):
                return None
            return self._backend.get(key)
        except Exception as exc:
            raise StorageUnavailableError(f"Unable to read trusted object {key}") from exc

    def list_prefix(self, prefix: str, *, max_keys: int = 1000) -> tuple[str, ...]:
        try:
            page = self._backend.list(prefix, max_keys=max_keys)
            return tuple(entry.key for entry in page.entries)
        except Exception as exc:
            raise StorageUnavailableError(f"Unable to list trusted prefix {prefix}") from exc

    def presign(self, key: str, *, expires_in: int = 900) -> str:
        try:
            return self._backend.get_url(key, expires_in=expires_in)
        except Exception as exc:
            raise StorageUnavailableError(f"Unable to mint URL for {key}") from exc
