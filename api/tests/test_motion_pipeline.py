from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from genblaze_core import Asset, FFmpegCompositor
from genblaze_core.testing import (
    MockAudioProvider,
    MockProvider,
    MockVideoProvider,
)

from dara.pipelines.motion import (
    MotionProviders,
    MotionSpec,
    build_motion_pipeline,
)


def asset(path: Path, media_type: str) -> Asset:
    data = path.read_bytes()
    return Asset(
        url=path.resolve().as_uri(),
        media_type=media_type,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        duration=1.0,
    )


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
class MotionPipelineTests(unittest.TestCase):
    def test_image_video_narration_fan_in_produces_verified_mp4(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            video_path = output_dir / "video.mp4"
            audio_path = output_dir / "narration.m4a"
            subprocess.run(
                [
                    "ffmpeg",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=navy:s=320x180:d=1",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-y",
                    str(video_path),
                ],
                check=True,
            )
            subprocess.run(
                [
                    "ffmpeg",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=1",
                    "-c:a",
                    "aac",
                    "-y",
                    str(audio_path),
                ],
                check=True,
            )

            keyframe = MockProvider(
                name="mock-image",
                assets=[
                    Asset(
                        url="memory://keyframe.png",
                        media_type="image/png",
                        sha256="1" * 64,
                    )
                ],
                cost_usd=0.01,
            )
            video = MockVideoProvider(
                assets=[asset(video_path, "video/mp4")],
                cost_usd=0.4,
            )
            audio = MockAudioProvider(
                assets=[asset(audio_path, "audio/mp4")],
                cost_usd=0.001,
            )
            pipeline = build_motion_pipeline(
                MotionSpec(
                    project_id="prj_motion_test",
                    keyframe_prompt="A cobalt cup on pale linen.",
                    video_prompt="A slow cinematic push toward the cobalt cup.",
                    narration="Quiet form, made visible.",
                ),
                output_dir=output_dir,
                providers=MotionProviders(
                    image=keyframe,
                    video=video,
                    audio=audio,
                    compositor=FFmpegCompositor(output_dir=output_dir),
                ),
            )

            result = pipeline.run(raise_on_failure=True)

            self.assertEqual(len(result.run.steps), 4)
            self.assertEqual(video.received_steps[0].inputs[0].media_type, "image/png")
            composite_inputs = result.run.steps[3].inputs
            self.assertEqual(
                {item.media_type.split("/", 1)[0] for item in composite_inputs},
                {"video", "audio"},
            )
            composite = result.run.steps[3].assets[0]
            self.assertEqual(composite.media_type, "video/mp4")
            self.assertTrue(Path(composite.url.removeprefix("file://")).exists())
            self.assertTrue(result.manifest.verify_hash())
            self.assertTrue(result.manifest.verify())
            self.assertEqual(
                result.run.steps[3].metadata["_input_from"],
                [1, 2],
            )
            self.assertTrue(result.run.steps[0].metadata["_fallback_models"])
            self.assertTrue(result.run.steps[1].metadata["_fallback_models"])
            self.assertTrue(result.run.steps[2].metadata["_fallback_models"])


if __name__ == "__main__":
    unittest.main()
