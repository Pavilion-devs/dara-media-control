from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from dara.jobs import LiveRunRecord
from dara.tools.provider_report import measurement, qa_latencies


class ProviderReportTests(unittest.TestCase):
    def test_measurement_reports_median_failures_and_slow_samples(self) -> None:
        result = measurement(
            provider="example",
            model="model",
            modality="image",
            latencies=[10.0, 20.0, 100.0],
            failures=1,
            unit_cost_usd=Decimal("0.010000"),
            cost_basis="test",
        )

        self.assertEqual(result.samples, 4)
        self.assertEqual(result.successful, 3)
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.p50_latency_s, 20.0)
        self.assertTrue(result.over_90s)

    def test_qa_latency_starts_after_the_image_step(self) -> None:
        started = datetime(2026, 7, 29, tzinfo=UTC)
        run = LiveRunRecord(
            job_id="job_report",
            project_id="prj_report",
            prompt="A production provider report fixture",
            aspect_ratio="1:1",
            policy_id="pol_standard",
            expected_cost_usd=Decimal("0.015000"),
            worst_case_cost_usd=Decimal("0.045000"),
        )
        run.append_event(
            "step.completed",
            "Image complete.",
            provider="openai-dalle",
            model="gpt-image-2",
            at=started,
        )
        run.append_event(
            "agent.iteration.evaluated",
            "QA passed.",
            provider="openai",
            model="gpt-4.1-mini",
            at=started + timedelta(seconds=7.25),
        )

        self.assertEqual(qa_latencies(run), [7.25])


if __name__ == "__main__":
    unittest.main()
