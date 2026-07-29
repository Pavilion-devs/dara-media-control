from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from genblaze_core import (
    Asset,
    ModelRegistry,
    ModelSpec,
    Modality,
    ProviderError,
    ProviderErrorCode,
    Step,
    SyncProvider,
)
from genblaze_core.providers import ProviderCapabilities
from genblaze_core.providers.pricing import per_unit


REPLICATE_IMAGE_MODEL = "black-forest-labs/flux-1.1-pro"
REPLICATE_IMAGE_PRICE_USD = 0.04
REPLICATE_API_ROOT = "https://api.replicate.com/v1"
MAX_IMAGE_BYTES = 50 * 1024 * 1024

_SIZE_TO_ASPECT_RATIO = {
    "1024x1024": "1:1",
    "1536x1024": "3:2",
    "1024x1536": "2:3",
}
_FORMAT_TO_MEDIA_TYPE = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}
_FORMAT_TO_EXTENSION = {
    "jpg": ".jpg",
    "jpeg": ".jpg",
    "png": ".png",
    "webp": ".webp",
}

JsonRequest = Callable[
    [str, str, dict[str, object] | None, dict[str, str]],
    dict[str, Any],
]
DownloadBytes = Callable[[str], tuple[bytes, str | None]]


def _error_code(status: int) -> ProviderErrorCode:
    if status in {401, 403}:
        return ProviderErrorCode.AUTH_FAILURE
    if status == 429:
        return ProviderErrorCode.RATE_LIMIT
    if status in {400, 404, 409, 422}:
        return ProviderErrorCode.INVALID_INPUT
    if status == 402:
        return ProviderErrorCode.MODEL_ERROR
    if status >= 500:
        return ProviderErrorCode.SERVER_ERROR
    return ProviderErrorCode.UNKNOWN


def _default_json_request(
    method: str,
    url: str,
    payload: dict[str, object] | None,
    headers: dict[str, str],
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=65.0) as response:
            value = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        retry_after = exc.headers.get("Retry-After")
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("detail")
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            detail = None
        raise ProviderError(
            f"Replicate request failed with HTTP {exc.code}"
            + (f": {detail}" if isinstance(detail, str) else "."),
            error_code=_error_code(exc.code),
            retry_after=float(retry_after) if retry_after else None,
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise ProviderError(
            "Replicate request could not reach the prediction service.",
            error_code=ProviderErrorCode.TIMEOUT,
        ) from exc
    if not isinstance(value, dict):
        raise ProviderError(
            "Replicate returned an invalid prediction document.",
            error_code=ProviderErrorCode.SERVER_ERROR,
        )
    return value


def _validate_output_url(value: str) -> None:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or not (
            host == "replicate.delivery"
            or host.endswith(".replicate.delivery")
        )
    ):
        raise ProviderError(
            "Replicate returned an unexpected output location.",
            error_code=ProviderErrorCode.SERVER_ERROR,
        )


def _validate_poll_url(value: str) -> None:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() != "api.replicate.com"
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ProviderError(
            "Replicate returned an unexpected prediction polling location.",
            error_code=ProviderErrorCode.SERVER_ERROR,
        )


def _default_download_bytes(url: str) -> tuple[bytes, str | None]:
    _validate_output_url(url)
    request = Request(url, headers={"User-Agent": "Dara/1.0"})
    try:
        with urlopen(request, timeout=60.0) as response:
            content_type = response.headers.get_content_type()
            data = response.read(MAX_IMAGE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ProviderError(
            "Replicate output could not be downloaded.",
            error_code=ProviderErrorCode.SERVER_ERROR,
        ) from exc
    if len(data) > MAX_IMAGE_BYTES:
        raise ProviderError(
            "Replicate output exceeded Dara's 50 MB image limit.",
            error_code=ProviderErrorCode.INVALID_INPUT,
        )
    if not data:
        raise ProviderError(
            "Replicate returned an empty image.",
            error_code=ProviderErrorCode.SERVER_ERROR,
        )
    return data, content_type


class ReplicateImageProvider(SyncProvider):
    """Minimal Genblaze provider for Replicate's official FLUX image model."""

    name = "replicate"

    @classmethod
    def create_registry(cls) -> ModelRegistry:
        registry = ModelRegistry()
        registry.register(
            ModelSpec(
                model_id=REPLICATE_IMAGE_MODEL,
                modality=Modality.IMAGE,
                pricing=per_unit(REPLICATE_IMAGE_PRICE_USD),
            )
        )
        return registry

    def __init__(
        self,
        *,
        api_token: str | None = None,
        output_dir: str | Path | None = None,
        http_timeout: float = 180.0,
        json_request: JsonRequest = _default_json_request,
        download_bytes: DownloadBytes = _default_download_bytes,
        models: ModelRegistry | None = None,
    ) -> None:
        super().__init__(models=models)
        self._api_token = api_token
        self._output_dir = Path(output_dir) if output_dir else None
        self._http_timeout = http_timeout
        self._json_request = json_request
        self._download_bytes = download_bytes

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported_modalities=[Modality.IMAGE],
            supported_inputs=["text"],
            accepts_chain_input=False,
            models=self.models.known(),
            output_formats=list(_FORMAT_TO_MEDIA_TYPE.values()),
        )

    def preflight_auth(self, *, timeout: float = 5.0) -> None:
        del timeout
        if not (self._api_token or os.getenv("REPLICATE_API_TOKEN")):
            raise ProviderError(
                "REPLICATE_API_TOKEN is not configured.",
                error_code=ProviderErrorCode.AUTH_FAILURE,
            )

    def _headers(self) -> dict[str, str]:
        token = self._api_token or os.getenv("REPLICATE_API_TOKEN")
        if not token:
            raise ProviderError(
                "REPLICATE_API_TOKEN is not configured.",
                error_code=ProviderErrorCode.AUTH_FAILURE,
            )
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "wait=60",
            "Cancel-After": f"{max(5, int(self._http_timeout))}s",
            "User-Agent": "Dara/1.0",
        }

    @staticmethod
    def _output_url(prediction: dict[str, Any]) -> str | None:
        output = prediction.get("output")
        if isinstance(output, str):
            return output
        if isinstance(output, list):
            return next((item for item in output if isinstance(item, str)), None)
        return None

    def _wait_for_prediction(
        self,
        prediction: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        started = time.monotonic()
        while str(prediction.get("status", "")).lower() in {
            "starting",
            "processing",
        }:
            if time.monotonic() - started >= self._http_timeout:
                raise ProviderError(
                    "Replicate prediction exceeded Dara's timeout.",
                    error_code=ProviderErrorCode.TIMEOUT,
                )
            urls = prediction.get("urls")
            poll_url = urls.get("get") if isinstance(urls, dict) else None
            if not isinstance(poll_url, str):
                raise ProviderError(
                    "Replicate did not return a prediction polling URL.",
                    error_code=ProviderErrorCode.SERVER_ERROR,
                )
            _validate_poll_url(poll_url)
            time.sleep(1.0)
            prediction = self._json_request("GET", poll_url, None, headers)
        return prediction

    def generate(self, step: Step, config: dict[str, Any] | None = None) -> Step:
        del config
        if step.model != REPLICATE_IMAGE_MODEL:
            raise ProviderError(
                f"Replicate image model is not configured: {step.model}",
                error_code=ProviderErrorCode.MODEL_ERROR,
            )
        if step.inputs:
            raise ProviderError(
                "The configured Replicate fallback supports text-to-image only.",
                error_code=ProviderErrorCode.INVALID_INPUT,
            )
        output_format = str(step.params.get("output_format", "webp")).lower()
        if output_format not in _FORMAT_TO_MEDIA_TYPE:
            raise ProviderError(
                f"Unsupported Replicate output format: {output_format}",
                error_code=ProviderErrorCode.INVALID_INPUT,
            )
        aspect_ratio = str(
            step.params.get(
                "aspect_ratio",
                _SIZE_TO_ASPECT_RATIO.get(str(step.params.get("size")), "1:1"),
            )
        )
        input_payload: dict[str, object] = {
            "prompt": step.prompt or "",
            "aspect_ratio": aspect_ratio,
            "output_format": output_format,
            "safety_tolerance": 2,
            "prompt_upsampling": False,
        }
        if step.seed is not None:
            input_payload["seed"] = step.seed

        headers = self._headers()
        prediction = self._json_request(
            "POST",
            (
                f"{REPLICATE_API_ROOT}/models/"
                f"{REPLICATE_IMAGE_MODEL}/predictions"
            ),
            {"input": input_payload},
            headers,
        )
        prediction = self._wait_for_prediction(prediction, headers)
        status = str(prediction.get("status", "")).lower()
        if status != "succeeded":
            message = prediction.get("error")
            raise ProviderError(
                "Replicate prediction failed"
                + (f": {message}" if isinstance(message, str) else "."),
                error_code=ProviderErrorCode.MODEL_ERROR,
            )
        output_url = self._output_url(prediction)
        if output_url is None:
            raise ProviderError(
                "Replicate prediction completed without an image.",
                error_code=ProviderErrorCode.SERVER_ERROR,
            )
        data, returned_type = self._download_bytes(output_url)
        requested_type = _FORMAT_TO_MEDIA_TYPE[output_format]
        media_type = (
            returned_type
            if returned_type in _FORMAT_TO_MEDIA_TYPE.values()
            else requested_type
        )
        extension = _FORMAT_TO_EXTENSION[
            next(
                key
                for key, value in _FORMAT_TO_MEDIA_TYPE.items()
                if value == media_type
            )
        ]
        output_dir = self._output_dir or Path(os.getenv("TMPDIR", "/tmp"))
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{step.step_id}-replicate{extension}"
        path.write_bytes(data)
        step.provider = self.name
        step.assets.append(
            Asset(
                url=path.resolve().as_uri(),
                media_type=media_type,
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data),
            )
        )
        step.provider_payload = {
            "id": prediction.get("id"),
            "status": status,
            "metrics": prediction.get("metrics"),
        }
        return step
