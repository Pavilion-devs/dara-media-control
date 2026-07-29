from __future__ import annotations

import unittest

from dara.tools.list_models import model_usages, render_markdown


class ModelInventoryTests(unittest.TestCase):
    def test_inventory_matches_the_configured_provider_routes(self) -> None:
        usages = model_usages()
        self.assertEqual(
            {item.provider for item in usages},
            {"OpenAI", "Replicate"},
        )
        self.assertEqual(
            {item.model for item in usages},
            {
                "gpt-image-2",
                "gpt-image-2-2026-04-21",
                "black-forest-labs/flux-1.1-pro",
                "sora-2",
                "sora-2-pro",
                "tts-1",
                "tts-1-hd",
                "gpt-4.1-mini",
            },
        )

    def test_markdown_distinguishes_production_and_integration_evidence(self) -> None:
        report = render_markdown()
        self.assertIn("Production calls persisted and verified in B2", report)
        self.assertIn("deterministic integration proof", report)
        self.assertIn("not a model provider", report)


if __name__ == "__main__":
    unittest.main()
