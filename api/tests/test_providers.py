from __future__ import annotations

import unittest
from decimal import Decimal

from genblaze_core import Modality
from genblaze_openai import DalleProvider, OpenAITTSProvider, SoraProvider

from dara.policy import PlannedStep, RunPlan, estimate_run_cost
from dara.providers import (
    ImageProviderRouter,
    POLICY_REGISTRY,
    provider_for,
    registry_for,
    route_for,
)


class ProviderFactoryTests(unittest.TestCase):
    def test_factory_builds_installed_provider_for_each_media_modality(self) -> None:
        self.assertIsInstance(provider_for(Modality.IMAGE), ImageProviderRouter)
        self.assertIsInstance(provider_for(Modality.VIDEO), SoraProvider)
        self.assertIsInstance(provider_for(Modality.AUDIO), OpenAITTSProvider)

    def test_every_media_route_has_a_fallback_chain(self) -> None:
        for modality in (Modality.IMAGE, Modality.VIDEO, Modality.AUDIO):
            route = route_for(modality)
            self.assertTrue(route.fallback_models)
            registry = registry_for(modality)
            self.assertIsNotNone(registry.get(route.primary_model).pricing)
            self.assertTrue(
                all(
                    registry.get(model).pricing is not None
                    for model in route.fallback_models
                )
            )

    def test_registry_fork_does_not_mutate_connector_defaults(self) -> None:
        configured = registry_for(Modality.IMAGE)
        self.assertIsNotNone(configured.get("gpt-image-2").pricing)
        self.assertIsNone(
            DalleProvider.models_default().get("gpt-image-2").pricing
        )

    def test_policy_registry_prices_image_video_audio_and_qa(self) -> None:
        cases = (
            (
                PlannedStep(
                    provider="openai",
                    model="gpt-image-2",
                    modality="image",
                    units=1,
                ),
                2,
                Decimal("0.020000"),
            ),
            (
                PlannedStep(
                    provider="openai",
                    model="sora-2",
                    modality="video",
                    units=4,
                ),
                2,
                Decimal("0.800000"),
            ),
            (
                PlannedStep(
                    provider="openai",
                    model="tts-1",
                    modality="audio",
                    units=1000,
                ),
                1,
                Decimal("0.015000"),
            ),
            (
                PlannedStep(
                    provider="openai",
                    model="gpt-4.1-mini",
                    modality="text",
                ),
                1,
                Decimal("0.005000"),
            ),
        )
        for index, (step, variants, expected) in enumerate(cases):
            with self.subTest(model=step.model):
                plan = RunPlan(
                    tenant_id="demo",
                    job_id=f"job_registry_{index}",
                    modality=step.modality,
                    aspect_ratio="1:1",
                    variants=variants,
                    max_attempts=1,
                    steps=(step,),
                )
                estimate = estimate_run_cost(plan, POLICY_REGISTRY)
                self.assertEqual(estimate.expected_usd, expected)
                self.assertEqual(estimate.unpriced_models, ())


if __name__ == "__main__":
    unittest.main()
