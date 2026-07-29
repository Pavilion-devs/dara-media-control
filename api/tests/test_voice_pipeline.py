from __future__ import annotations

import threading
import time
import tempfile
import unittest
from pathlib import Path

from genblaze_core.testing import MockAudioProvider

from dara.pipelines.voice import VoicePackSpec, run_voice_pack


class ConcurrentAudioProvider(MockAudioProvider):
    def __init__(self) -> None:
        super().__init__(cost_usd=0.001)
        self._concurrency_lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def generate(self, step, config=None):
        with self._concurrency_lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(0.03)
            return super().generate(step, config)
        finally:
            with self._concurrency_lock:
                self.active -= 1


class VoicePipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_script_runs_as_parallel_verified_voice_variants(self) -> None:
        provider = ConcurrentAudioProvider()
        spec = VoicePackSpec(
            project_id="prj_voice_test",
            script="Dara keeps every generation governed and verifiable.",
            voices=("alloy", "coral", "onyx"),
            max_concurrency=3,
        )
        with tempfile.TemporaryDirectory() as temporary:
            results = await run_voice_pack(
                spec,
                output_dir=Path(temporary),
                provider=provider,
            )

        self.assertEqual(len(results), 3)
        self.assertGreaterEqual(provider.max_active, 2)
        self.assertEqual(
            [result.run.steps[0].params["voice"] for result in results],
            list(spec.voices),
        )
        self.assertEqual(
            [
                result.run.steps[0].metadata["voice_pack_index"]
                for result in results
            ],
            [0, 1, 2],
        )
        self.assertTrue(
            all(result.run.steps[0].metadata["_fallback_models"] for result in results)
        )
        self.assertTrue(all(result.manifest.verify_hash() for result in results))
        self.assertTrue(all(result.manifest.verify() for result in results))

    def test_voice_pack_rejects_duplicates_and_unknown_voices(self) -> None:
        with self.assertRaises(ValueError):
            VoicePackSpec(
                project_id="prj_voice_test",
                script="A short script.",
                voices=("alloy", "alloy"),
            )
        with self.assertRaises(ValueError):
            VoicePackSpec(
                project_id="prj_voice_test",
                script="A short script.",
                voices=("not-a-real-voice",),
            )


if __name__ == "__main__":
    unittest.main()
