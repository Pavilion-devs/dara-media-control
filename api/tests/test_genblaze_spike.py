import unittest

from dara.tools.sdk_spike import run_spike


class GenblazeSpikeTests(unittest.TestCase):
    def test_no_key_pipeline_emits_valid_manifest(self) -> None:
        result = run_spike()
        self.assertEqual(result["step_count"], 1)
        self.assertTrue(result["verify_hash"])
        self.assertTrue(result["verify"])
        self.assertEqual(len(result["canonical_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
