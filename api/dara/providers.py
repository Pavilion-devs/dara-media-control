from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from genblaze_core import ModelRegistry, ModelSpec, Modality
from genblaze_core.providers import BaseProvider
from genblaze_core.providers.pricing import (
    per_input_chars,
    per_output_second,
    per_unit,
)
from genblaze_openai import DalleProvider, OpenAITTSProvider, SoraProvider


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
        fallback_models=("gpt-image-2-2026-04-21",),
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
        return DalleProvider(
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
    for route in ROUTES.values():
        if model == route.primary_model:
            return route.price_usd
        if model in route.fallback_models and route.modality is Modality.IMAGE:
            return route.price_usd
    if model == "gpt-4.1-mini":
        return Decimal("0.005000")
    return None
