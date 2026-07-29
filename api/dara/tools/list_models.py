from __future__ import annotations

from dataclasses import dataclass

from genblaze_core import Modality

from dara.providers import ROUTES, provider_name_for_model
from dara.replicate_provider import REPLICATE_IMAGE_MODEL


@dataclass(frozen=True)
class ModelUsage:
    provider: str
    model: str
    modality: str
    role: str
    evidence: str


EVIDENCE = {
    "gpt-image-2": "Production calls persisted and verified in B2",
    "gpt-image-2-2026-04-21": "Configured fallback; account catalog verified",
    REPLICATE_IMAGE_MODEL: (
        "Provider adapter and deterministic contract tests; live probe pending"
    ),
    "sora-2": "Pipeline implemented; deterministic integration proof",
    "sora-2-pro": "Configured fallback; deterministic integration proof",
    "tts-1": "Pipeline implemented; deterministic integration proof",
    "tts-1-hd": "Configured fallback; deterministic integration proof",
    "gpt-4.1-mini": "Production prompt-expansion and vision-QA calls",
}


def model_usages() -> list[ModelUsage]:
    values: list[ModelUsage] = []
    for modality in (Modality.IMAGE, Modality.VIDEO, Modality.AUDIO):
        route = ROUTES[modality]
        values.append(
            ModelUsage(
                provider="OpenAI",
                model=route.primary_model,
                modality=modality.value,
                role="Primary",
                evidence=EVIDENCE[route.primary_model],
            )
        )
        values.extend(
            ModelUsage(
                provider=(
                    "OpenAI"
                    if provider_name_for_model(model) == "openai"
                    else "Replicate"
                ),
                model=model,
                modality=modality.value,
                role="Fallback",
                evidence=EVIDENCE[model],
            )
            for model in route.fallback_models
        )
    values.append(
        ModelUsage(
            provider="OpenAI",
            model="gpt-4.1-mini",
            modality="text + vision",
            role="Prompt expansion and visual QA",
            evidence=EVIDENCE["gpt-4.1-mini"],
        )
    )
    return values


def render_markdown() -> str:
    rows = [
        "# Providers and models",
        "",
        "Generated from `api/dara/providers.py`. OpenAI is Dara's primary AI provider;",
        "Replicate is the provider-diverse image fallback. Genblaze is the orchestration",
        "and provenance SDK, not a model provider.",
        "",
        "| Provider | Model | Modality | Role | Evidence |",
        "|---|---|---|---|---|",
    ]
    rows.extend(
        f"| {item.provider} | `{item.model}` | {item.modality} | "
        f"{item.role} | {item.evidence} |"
        for item in model_usages()
    )
    rows.extend(
        [
            "",
            "The motion pipeline also uses Genblaze `FFmpegCompositor` for deterministic",
            "local audio/video fan-in. Committed demo fixtures use visibly named mock",
            "providers and never masquerade as live AI-provider execution.",
            "",
        ]
    )
    return "\n".join(rows)


def main() -> None:
    print(render_markdown(), end="")


if __name__ == "__main__":
    main()
