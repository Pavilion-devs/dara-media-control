from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from genblaze_core import (
    FFmpegCompositor,
    LoggingTracer,
    Modality,
    Pipeline,
    StepType,
)
from genblaze_core.providers import BaseProvider
from pydantic import BaseModel, ConfigDict, Field

from ..providers import provider_for, route_for


class MotionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = "demo"
    project_id: str
    keyframe_prompt: str = Field(min_length=8, max_length=4000)
    video_prompt: str = Field(min_length=8, max_length=4000)
    narration: str = Field(min_length=1, max_length=2000)
    seconds: int = Field(default=4, ge=4, le=4)
    size: str = "1280x720"
    voice: str = "alloy"


@dataclass(frozen=True)
class MotionProviders:
    image: BaseProvider
    video: BaseProvider
    audio: BaseProvider
    compositor: BaseProvider


def default_motion_providers(output_dir: str | Path) -> MotionProviders:
    return MotionProviders(
        image=provider_for(
            Modality.IMAGE,
            output_dir=output_dir,
            http_timeout=180.0,
        ),
        video=provider_for(
            Modality.VIDEO,
            output_dir=output_dir,
            http_timeout=240.0,
        ),
        audio=provider_for(
            Modality.AUDIO,
            output_dir=output_dir,
            http_timeout=120.0,
        ),
        compositor=FFmpegCompositor(
            output_dir=output_dir,
            timeout=120.0,
        ),
    )


def build_motion_pipeline(
    spec: MotionSpec,
    *,
    output_dir: str | Path,
    providers: MotionProviders | None = None,
) -> Pipeline:
    resolved = providers or default_motion_providers(output_dir)
    image_route = route_for(Modality.IMAGE)
    video_route = route_for(Modality.VIDEO)
    audio_route = route_for(Modality.AUDIO)

    return (
        Pipeline(
            "motion-spot",
            tenant_id=spec.tenant_id,
            project_id=spec.project_id,
            chain=False,
            tracer=LoggingTracer(),
        )
        .step(
            resolved.image,
            model=image_route.primary_model,
            fallback_models=list(image_route.fallback_models),
            prompt=spec.keyframe_prompt,
            modality=Modality.IMAGE,
            size="1536x1024",
            quality="low",
            output_format="png",
            n=1,
            expected_duration_sec=22.0,
            metadata={"motion_role": "keyframe"},
        )
        .step(
            resolved.video,
            model=video_route.primary_model,
            fallback_models=list(video_route.fallback_models),
            prompt=spec.video_prompt,
            modality=Modality.VIDEO,
            input_from=0,
            seconds=spec.seconds,
            size=spec.size,
            expected_duration_sec=90.0,
            metadata={"motion_role": "video"},
        )
        .step(
            resolved.audio,
            model=audio_route.primary_model,
            fallback_models=list(audio_route.fallback_models),
            prompt=spec.narration,
            modality=Modality.AUDIO,
            voice=spec.voice,
            response_format="mp3",
            expected_duration_sec=12.0,
            metadata={"motion_role": "narration"},
        )
        .step(
            resolved.compositor,
            model="ffmpeg-copy",
            prompt=None,
            modality=Modality.VIDEO,
            step_type=StepType.MIX,
            input_from=[1, 2],
            expected_duration_sec=5.0,
            metadata={"motion_role": "composite"},
        )
    )
