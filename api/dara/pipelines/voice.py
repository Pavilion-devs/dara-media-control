from __future__ import annotations

from pathlib import Path

from genblaze_core import LoggingTracer, Modality, Pipeline, PipelineResult
from genblaze_core.providers import BaseProvider
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..providers import provider_for, route_for


OPENAI_VOICES = (
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "fable",
    "nova",
    "onyx",
    "sage",
    "shimmer",
    "verse",
)


class VoicePackSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = "demo"
    project_id: str
    script: str = Field(min_length=1, max_length=4096)
    voices: tuple[str, ...] = ("alloy", "coral", "onyx")
    response_format: str = "mp3"
    max_concurrency: int = Field(default=4, ge=1, le=8)

    @field_validator("voices")
    @classmethod
    def validate_voices(cls, voices: tuple[str, ...]) -> tuple[str, ...]:
        if not 1 <= len(voices) <= 8:
            raise ValueError("A voice pack must contain between 1 and 8 voices.")
        if len(set(voices)) != len(voices):
            raise ValueError("Voice pack voices must be unique.")
        unsupported = sorted(set(voices) - set(OPENAI_VOICES))
        if unsupported:
            raise ValueError(f"Unsupported OpenAI voice(s): {', '.join(unsupported)}.")
        return voices


def build_voice_pipeline(
    spec: VoicePackSpec,
    *,
    output_dir: str | Path,
    provider: BaseProvider | None = None,
) -> Pipeline:
    route = route_for(Modality.AUDIO)
    resolved = provider or provider_for(
        Modality.AUDIO,
        output_dir=output_dir,
        http_timeout=120.0,
    )
    return Pipeline(
        "voiceover-pack",
        tenant_id=spec.tenant_id,
        project_id=spec.project_id,
        tracer=LoggingTracer(),
    ).step(
        resolved,
        model=route.primary_model,
        fallback_models=list(route.fallback_models),
        prompt=spec.script,
        modality=Modality.AUDIO,
        voice=spec.voices[0],
        response_format=spec.response_format,
        expected_duration_sec=12.0,
        metadata={
            "voice_pack_size": len(spec.voices),
            "voice_pack_index": 0,
            "voice": spec.voices[0],
        },
    )


async def run_voice_pack(
    spec: VoicePackSpec,
    *,
    output_dir: str | Path,
    provider: BaseProvider | None = None,
) -> list[PipelineResult]:
    pipeline = build_voice_pipeline(
        spec,
        output_dir=output_dir,
        provider=provider,
    )
    items = [
        {
            "voice": voice,
            "metadata": {
                "voice_pack_size": len(spec.voices),
                "voice_pack_index": index,
                "voice": voice,
            },
        }
        for index, voice in enumerate(spec.voices)
    ]
    return await pipeline.abatch_run(
        items=items,
        max_concurrency=min(spec.max_concurrency, len(items)),
        raise_on_failure=True,
        timeout=120.0,
        pipeline_timeout=150.0,
    )
