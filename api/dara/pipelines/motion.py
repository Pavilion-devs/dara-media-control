from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from genblaze_core import (
    Asset,
    FFmpegCompositor,
    FFmpegTransform,
    LoggingTracer,
    Modality,
    Pipeline,
    ProviderCapabilities,
    ProviderError,
    ProviderErrorCode,
    Step,
    StepType,
)
from genblaze_core._utils import local_file_url
from genblaze_core.providers._ffmpeg_utils import (
    get_output_path,
    populate_file_asset_integrity,
    resolve_ffmpeg,
    resolve_input_path,
    run_ffmpeg,
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
    keyframe_transform: BaseProvider | None = None


class SoraKeyframeTransform(FFmpegTransform):
    """Fit generated stills to Sora's exact input-reference dimensions."""

    name = "dara-keyframe-transform"

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported_modalities=[Modality.IMAGE],
            supported_inputs=["image"],
            accepts_chain_input=True,
            output_formats=["image/png", "image/jpeg", "image/webp"],
        )

    def _build_resize_cmd(
        self,
        ffmpeg_bin: str,
        input_path: str,
        out_path: str,
        params: dict,
    ) -> list[str]:
        width = int(params["width"])
        height = int(params["height"])
        fit = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1"
        )
        return [ffmpeg_bin, "-i", input_path, "-vf", fit, "-y", out_path]


class DaraMotionCompositor(FFmpegCompositor):
    """Prepend the generated still, then mux narration over the Sora clip."""

    name = "dara-motion-compositor"

    def generate(self, step: Step, config: object | None = None) -> Step:
        del config
        image = next(
            (item for item in step.inputs if item.media_type.startswith("image/")),
            None,
        )
        video = next(
            (item for item in step.inputs if item.media_type.startswith("video/")),
            None,
        )
        audio = next(
            (item for item in step.inputs if item.media_type.startswith("audio/")),
            None,
        )
        if image is None or video is None or audio is None:
            raise ProviderError(
                "Motion composition requires image, video, and audio inputs.",
                error_code=ProviderErrorCode.INVALID_INPUT,
            )
        roots = [self._output_dir] if self._output_dir else None
        image_path = resolve_input_path(image.url, extra_roots=roots)
        video_path = resolve_input_path(video.url, extra_roots=roots)
        audio_path = resolve_input_path(audio.url, extra_roots=roots)
        output_path = get_output_path(step.step_id, "mp4", self._output_dir)
        ffmpeg = resolve_ffmpeg(self._ffmpeg_path)
        filter_graph = (
            "[0:v]loop=loop=-1:size=1:start=0,trim=duration=1,"
            "setpts=PTS-STARTPTS,fps=30,setsar=1,format=yuv420p[still];"
            "[1:v]scale=1280:720,setsar=1,fps=30,format=yuv420p[clip];"
            "[still][clip]concat=n=2:v=1:a=0[visual];[2:a]apad[audio]"
        )
        run_ffmpeg(
            [
                ffmpeg,
                "-loglevel",
                "error",
                "-i",
                str(image_path),
                "-i",
                str(video_path),
                "-i",
                str(audio_path),
                "-filter_complex",
                filter_graph,
                "-map",
                "[visual]",
                "-map",
                "[audio]",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                "-y",
                str(output_path),
            ],
            timeout=self._timeout,
        )
        asset = Asset(
            url=local_file_url(output_path.resolve()),
            media_type="video/mp4",
            width=1280,
            height=720,
            duration=(video.duration or 4.0) + 1.0,
        )
        populate_file_asset_integrity(asset, output_path)
        step.assets.append(asset)
        step.step_type = StepType.MIX
        return step


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
        compositor=DaraMotionCompositor(
            output_dir=output_dir,
            timeout=120.0,
        ),
        keyframe_transform=SoraKeyframeTransform(
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
    keyframe_transform = resolved.keyframe_transform or SoraKeyframeTransform(
        output_dir=output_dir,
        timeout=120.0,
    )
    width, height = (int(part) for part in spec.size.split("x", 1))

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
            keyframe_transform,
            model="ffmpeg-sora-keyframe",
            prompt=None,
            modality=Modality.IMAGE,
            step_type=StepType.TRANSCODE,
            input_from=0,
            operation="resize",
            width=width,
            height=height,
            expected_duration_sec=3.0,
            metadata={"motion_role": "keyframe-normalize"},
        )
        .step(
            resolved.video,
            model=video_route.primary_model,
            fallback_models=list(video_route.fallback_models),
            prompt=spec.video_prompt,
            modality=Modality.VIDEO,
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
            input_from=[1, 2, 3],
            expected_duration_sec=5.0,
            metadata={"motion_role": "composite"},
        )
    )
