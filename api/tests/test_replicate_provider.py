from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genblaze_core import (
    Asset,
    Modality,
    Pipeline,
    ProviderError,
    ProviderErrorCode,
    Step,
    StepStatus,
    SyncProvider,
)

from dara.providers import ImageProviderRouter
from dara.replicate_provider import (
    REPLICATE_IMAGE_MODEL,
    ReplicateImageProvider,
)


class StubProvider(SyncProvider):
    def __init__(
        self,
        *,
        name: str,
        status: StepStatus,
        error_code: ProviderErrorCode | None = None,
    ) -> None:
        super().__init__()
        self.name = name
        self._status = status
        self._error_code = error_code
        self.calls: list[str] = []

    def generate(self, step: Step, config: object | None = None) -> Step:
        del config
        self.calls.append(step.model)
        if self._status is StepStatus.FAILED:
            raise ProviderError(
                "stub failure",
                error_code=self._error_code,
            )
        step.provider = self.name
        step.assets.append(
            Asset(
                url=Path(__file__).resolve().as_uri(),
                media_type="image/png",
                sha256="a" * 64,
                size_bytes=1,
            )
        )
        return step


class ReplicateProviderTests(unittest.TestCase):
    def test_official_prediction_is_downloaded_to_a_durable_local_asset(self) -> None:
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def request_json(
            method: str,
            url: str,
            payload: dict[str, object] | None,
            headers: dict[str, str],
        ) -> dict[str, object]:
            self.assertTrue(headers["Authorization"].startswith("Bearer "))
            calls.append((method, url, payload))
            return {
                "id": "pred_test",
                "status": "succeeded",
                "output": "https://replicate.delivery/test/image.png",
                "metrics": {"predict_time": 1.25},
            }

        with tempfile.TemporaryDirectory() as temporary:
            provider = ReplicateImageProvider(
                api_token="r8_test",
                output_dir=temporary,
                json_request=request_json,
                download_bytes=lambda _: (b"replicate-image", "image/png"),
            )
            step = Step(
                provider="replicate",
                model=REPLICATE_IMAGE_MODEL,
                modality=Modality.IMAGE,
                prompt="A precise production image prompt",
                params={
                    "size": "1536x1024",
                    "output_format": "png",
                },
            )
            result = provider.invoke(step)

            self.assertEqual(result.status, StepStatus.SUCCEEDED)
            self.assertEqual(result.provider, "replicate")
            self.assertEqual(result.cost_usd, 0.04)
            self.assertEqual(result.assets[0].media_type, "image/png")
            self.assertTrue(
                Path(result.assets[0].url.removeprefix("file://")).exists()
            )
            self.assertEqual(
                calls[0][2],
                {
                    "input": {
                        "prompt": "A precise production image prompt",
                        "aspect_ratio": "3:2",
                        "output_format": "png",
                        "safety_tolerance": 2,
                        "prompt_upsampling": False,
                    }
                },
            )

    def test_router_dispatches_replicate_model_to_second_provider(self) -> None:
        openai = StubProvider(name="openai-dalle", status=StepStatus.SUCCEEDED)
        replicate = StubProvider(name="replicate", status=StepStatus.SUCCEEDED)
        router = ImageProviderRouter(
            openai_provider=openai,
            replicate_provider=replicate,
        )
        result = router.invoke(
            Step(
                provider="dara-image-router",
                model=REPLICATE_IMAGE_MODEL,
                modality=Modality.IMAGE,
                prompt="A provider-diverse fallback fixture",
            )
        )

        self.assertEqual(openai.calls, [])
        self.assertEqual(replicate.calls, [REPLICATE_IMAGE_MODEL])
        self.assertEqual(result.provider, "replicate")

    def test_prediction_poll_url_cannot_exfiltrate_the_api_token(self) -> None:
        provider = ReplicateImageProvider(
            api_token="r8_test",
            json_request=lambda *_: {
                "status": "processing",
                "urls": {"get": "https://attacker.example/prediction"},
            },
        )
        result = provider.invoke(
            Step(
                provider="replicate",
                model=REPLICATE_IMAGE_MODEL,
                modality=Modality.IMAGE,
                prompt="A polling URL security fixture",
            )
        )

        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.error_code, ProviderErrorCode.SERVER_ERROR)

    def test_genblaze_fallback_chain_crosses_provider_boundary(self) -> None:
        openai = StubProvider(
            name="openai-dalle",
            status=StepStatus.FAILED,
            error_code=ProviderErrorCode.MODEL_ERROR,
        )
        replicate = StubProvider(name="replicate", status=StepStatus.SUCCEEDED)
        router = ImageProviderRouter(
            openai_provider=openai,
            replicate_provider=replicate,
        )
        result = (
            Pipeline(
                "provider-diverse-image-fixture",
                tenant_id="demo",
                project_id="prj_provider_test",
            )
            .step(
                router,
                model="gpt-image-2",
                fallback_models=[
                    "gpt-image-2-2026-04-21",
                    REPLICATE_IMAGE_MODEL,
                ],
                modality=Modality.IMAGE,
                prompt="A Genblaze provider-diverse fallback fixture",
            )
            .run(raise_on_failure=True)
        )

        final = result.run.steps[0]
        self.assertEqual(
            openai.calls,
            ["gpt-image-2", "gpt-image-2-2026-04-21"],
        )
        self.assertEqual(replicate.calls, [REPLICATE_IMAGE_MODEL])
        self.assertEqual(final.provider, "replicate")
        self.assertEqual(final.model, REPLICATE_IMAGE_MODEL)
        self.assertEqual(final.metadata["fallback_from"], "gpt-image-2")
        self.assertEqual(
            final.metadata["fallback_model"],
            REPLICATE_IMAGE_MODEL,
        )


if __name__ == "__main__":
    unittest.main()
