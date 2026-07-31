from __future__ import annotations

import unittest
from decimal import Decimal
from types import SimpleNamespace

from genblaze_core import Modality

from dara.policy import Severity
from dara.tools.seed_production_evidence import (
    ACTION_MAXIMUMS,
    admit,
    locked_policy,
    step_cost,
)


class ProductionEvidenceSeedTests(unittest.IsolatedAsyncioTestCase):
    async def test_motion_plan_is_bounded_and_locked_policy_blocks_without_spend(self) -> None:
        _, allowed_estimate, allowed = await admit(
            job_id="job_seed_allowed",
            project_id="prj_atlas_brand",
            modalities=(Modality.IMAGE, Modality.VIDEO, Modality.AUDIO),
        )
        _, blocked_estimate, blocked = await admit(
            job_id="job_seed_blocked",
            project_id="prj_atlas_brand",
            modalities=(Modality.VIDEO,),
            policy=locked_policy(),
        )

        self.assertIsNot(allowed.outcome, Severity.BLOCK)
        self.assertLessEqual(allowed_estimate.worst_case_usd, ACTION_MAXIMUMS["motion"])
        self.assertIs(blocked.outcome, Severity.BLOCK)
        self.assertGreater(blocked_estimate.expected_usd, 1)

    def test_missing_provider_cost_uses_explicit_registry_estimate(self) -> None:
        video = SimpleNamespace(
            cost_usd=None,
            modality=Modality.VIDEO,
            model="sora-2",
            params={"seconds": 4},
            prompt="A slow camera move.",
        )
        voice = SimpleNamespace(
            cost_usd=None,
            modality=Modality.AUDIO,
            model="tts-1",
            params={},
            prompt="x" * 100,
        )

        self.assertEqual(step_cost(video), (Decimal("0.400000"), "estimated"))
        self.assertEqual(str(step_cost(voice)[0]), "0.001500")
        self.assertEqual(step_cost(voice)[1], "estimated")

    def test_local_media_steps_never_inherit_provider_prices(self) -> None:
        keyframe = SimpleNamespace(
            cost_usd=None,
            modality=Modality.IMAGE,
            model="ffmpeg-sora-keyframe",
            params={},
            prompt=None,
        )
        composite = SimpleNamespace(
            cost_usd=None,
            modality=Modality.VIDEO,
            model="ffmpeg-copy",
            params={},
            prompt=None,
        )

        self.assertEqual(step_cost(keyframe), (Decimal("0.000000"), "known"))
        self.assertEqual(step_cost(composite), (Decimal("0.000000"), "known"))


if __name__ == "__main__":
    unittest.main()
