from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from genblaze_core import (
    ModelRegistry,
    ModelSpec,
    Modality,
    ProviderError,
    ProviderErrorCode,
    Step,
    SyncProvider,
)
from genblaze_core.providers import BaseProvider
from genblaze_core.providers.pricing import (
    per_input_chars,
    per_output_second,
    per_unit,
)
from genblaze_openai import DalleProvider, OpenAITTSProvider, SoraProvider

from .replicate_provider import (
    REPLICATE_IMAGE_MODEL,
    REPLICATE_IMAGE_PRICE_USD,
    ReplicateImageProvider,
)


@dataclass(frozen=True)
class ProviderRoute:
    modality: Modality
    provider: str
    primary_model: str
    fallback_models: tuple[str, ...]
    price_usd: Decimal
    price_unit: str
    pricing_basis: str


ROUTES = {
    Modality.IMAGE: ProviderRoute(
        modality=Modality.IMAGE,
        provider="openai",
        primary_model="gpt-image-2",
        fallback_models=(
            "gpt-image-2-2026-04-21",
            REPLICATE_IMAGE_MODEL,
        ),
        price_usd=Decimal("0.010000"),
        price_unit="image",
        pricing_basis="conservative low-quality image reservation",
    ),
    Modality.VIDEO: ProviderRoute(
        modality=Modality.VIDEO,
        provider="openai",
        primary_model="sora-2",
        fallback_models=("sora-2-pro",),
        price_usd=Decimal("0.100000"),
        price_unit="output_second",
        pricing_basis="720p output-second pricing",
    ),
    Modality.AUDIO: ProviderRoute(
        modality=Modality.AUDIO,
        provider="openai",
        primary_model="tts-1",
        fallback_models=("tts-1-hd",),
        price_usd=Decimal("0.015000"),
        price_unit="1000_input_characters",
        pricing_basis="input-character pricing",
    ),
}

UNIT_RESERVATIONS = {
    "gpt-image-2": Decimal("0.010000"),
    "gpt-image-2-2026-04-21": Decimal("0.010000"),
    REPLICATE_IMAGE_MODEL: Decimal("0.040000"),
    "sora-2": Decimal("0.100000"),
    "sora-2-pro": Decimal("0.300000"),
    "tts-1": Decimal("0.015000"),
    "tts-1-hd": Decimal("0.030000"),
    "gpt-4.1-mini": Decimal("0.005000"),
}


def route_for(modality: Modality) -> ProviderRoute:
    try:
        return ROUTES[modality]
    except KeyError as exc:
        raise ValueError(
            f"No generative provider route is configured for {modality.value}."
        ) from exc


def registry_for(modality: Modality) -> ModelRegistry:
    if modality is Modality.IMAGE:
        registry = DalleProvider.models_default().fork()
        registry.register(
            ModelSpec(
                model_id="gpt-image-2-2026-04-21",
                modality=Modality.IMAGE,
            )
        )
        registry.register_pricing("gpt-image-2", per_unit(0.01))
        registry.register_pricing(
            "gpt-image-2-2026-04-21",
            per_unit(0.01),
        )
        registry.register(
            ModelSpec(
                model_id=REPLICATE_IMAGE_MODEL,
                modality=Modality.IMAGE,
                pricing=per_unit(REPLICATE_IMAGE_PRICE_USD),
            )
        )
        return registry
    if modality is Modality.VIDEO:
        registry = SoraProvider.models_default().fork()
        registry.register_pricing("sora-2", per_output_second(0.10))
        registry.register_pricing("sora-2-pro", per_output_second(0.30))
        return registry
    if modality is Modality.AUDIO:
        registry = OpenAITTSProvider.models_default().fork()
        registry.register_pricing(
            "tts-1",
            per_input_chars(0.015, per=1000),
        )
        registry.register_pricing(
            "tts-1-hd",
            per_input_chars(0.030, per=1000),
        )
        return registry
    raise ValueError(
        f"No generative model registry is configured for {modality.value}."
    )


def build_policy_registry() -> ModelRegistry:
    registry = ModelRegistry()
    for modality in (Modality.IMAGE, Modality.VIDEO, Modality.AUDIO):
        provider_registry = registry_for(modality)
        route = route_for(modality)
        for model_id in (route.primary_model, *route.fallback_models):
            registry.register(provider_registry.get(model_id))
    registry.register(
        ModelSpec(
            model_id="gpt-4.1-mini",
            modality=Modality.TEXT,
            pricing=per_unit(0.005),
        )
    )
    return registry


POLICY_REGISTRY = build_policy_registry()


def provider_for(
    modality: Modality,
    *,
    output_dir: str | Path | None = None,
    http_timeout: float = 180.0,
) -> BaseProvider:
    registry = registry_for(modality)
    if modality is Modality.IMAGE:
        return ImageProviderRouter(
            output_dir=output_dir,
            http_timeout=http_timeout,
            models=registry,
        )
    if modality is Modality.VIDEO:
        return SoraProvider(
            output_dir=output_dir,
            http_timeout=http_timeout,
            models=registry,
        )
    if modality is Modality.AUDIO:
        return OpenAITTSProvider(
            output_dir=output_dir,
            http_timeout=http_timeout,
            models=registry,
        )
    raise ValueError(
        f"No generative provider is configured for {modality.value}."
    )


def unit_reservation(model: str) -> Decimal | None:
    return UNIT_RESERVATIONS.get(model)


def route_reservation(modality: Modality) -> Decimal:
    route = route_for(modality)
    return sum(
        (
            unit_reservation(model) or Decimal("0")
            for model in (route.primary_model, *route.fallback_models)
        ),
        start=Decimal("0"),
    ).quantize(Decimal("0.000001"))


def provider_name_for_model(model: str) -> str:
    return "replicate" if model == REPLICATE_IMAGE_MODEL else "openai"


class ImageProviderRouter(SyncProvider):
    """Route one Genblaze fallback chain across OpenAI and Replicate."""

    name = "dara-image-router"

    def __init__(
        self,
        *,
        output_dir: str | Path | None = None,
        http_timeout: float = 180.0,
        models: ModelRegistry | None = None,
        openai_provider: BaseProvider | None = None,
        replicate_provider: BaseProvider | None = None,
    ) -> None:
        super().__init__(models=models)
        self._http_timeout = http_timeout
        self._openai = openai_provider or DalleProvider(
            output_dir=output_dir,
            http_timeout=http_timeout,
            models=registry_for(Modality.IMAGE),
        )
        self._replicate = replicate_provider or ReplicateImageProvider(
            output_dir=output_dir,
            http_timeout=http_timeout,
        )

    def generate(self, step: Step, config: object | None = None) -> Step:
        del config
        is_replicate = step.model == REPLICATE_IMAGE_MODEL
        delegate = self._replicate if is_replicate else self._openai
        step.provider = provider_name_for_model(step.model)
        result = delegate.invoke(
            step,
            {
                "timeout": self._http_timeout,
                "max_retries": 2,
            },
        )
        if result.status.value == "succeeded":
            result.provider = provider_name_for_model(result.model)
            return result
        error_code = result.error_code or ProviderErrorCode.UNKNOWN
        if not is_replicate:
            error_code = ProviderErrorCode.MODEL_ERROR
        raise ProviderError(
            result.error or f"{result.provider} image generation failed.",
            error_code=error_code,
        )
