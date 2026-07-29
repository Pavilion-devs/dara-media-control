from __future__ import annotations

import json
import unittest
from decimal import Decimal
from pathlib import Path

from dara.tools.seed_demo import build_corpus


class DemoSeedTests(unittest.TestCase):
    def test_committed_corpus_matches_generator_and_required_story(self) -> None:
        generated = build_corpus()
        path = Path(__file__).resolve().parents[1] / "seeds" / "demo-runs.json"
        committed = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(committed, generated)

        runs = committed["runs"]
        self.assertGreaterEqual(len(runs), 12)
        self.assertLessEqual(len(runs), 15)
        self.assertEqual(len({run["seed_id"] for run in runs}), len(runs))
        self.assertGreaterEqual(
            sum(run["outcome"] == "blocked" for run in runs),
            2,
        )
        self.assertTrue(
            any(
                run["outcome"] == "succeeded"
                and run["qa_attempts"] >= 2
                and any(event["type"] == "qa.revised" for event in run["events"])
                for run in runs
            )
        )
        self.assertTrue(
            {"still-campaign", "motion-spot", "voiceover-pack"}
            <= {run["pipeline_id"] for run in runs}
        )
        for run in runs:
            with self.subTest(seed_id=run["seed_id"]):
                self.assertEqual(
                    [event["at_ms"] for event in run["events"]],
                    sorted(event["at_ms"] for event in run["events"]),
                )
                Decimal(run["cost_usd"])
                Decimal(run["saved_cost_usd"])


if __name__ == "__main__":
    unittest.main()
