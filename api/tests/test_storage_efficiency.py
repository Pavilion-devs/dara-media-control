from __future__ import annotations

import json
import unittest
from decimal import Decimal
from types import SimpleNamespace

from dara.jobs import B2LiveRunStore, LiveRunRecord, live_run_key
from dara.storage import DaraStorage


class CountingBackend:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.get_calls = 0
        self.exists_calls = 0

    def put(self, key, data, **kwargs):
        del kwargs
        self.objects[key] = bytes(data)
        return key

    def get(self, key):
        self.get_calls += 1
        return self.objects[key]

    def exists(self, key):
        self.exists_calls += 1
        return key in self.objects

    def list(self, prefix="", **kwargs):
        del kwargs
        entries = [
            SimpleNamespace(key=key)
            for key in sorted(self.objects)
            if key.startswith(prefix)
        ]
        return SimpleNamespace(entries=entries)

    def get_url(self, key, *, expires_in=3600):
        return f"memory://{key}?expires={expires_in}"


def run_record(job_id: str = "job_cache_test") -> LiveRunRecord:
    return LiveRunRecord(
        job_id=job_id,
        project_id="prj_test",
        prompt="Cache this durable record",
        aspect_ratio="1:1",
        policy_id="pol_standard",
        expected_cost_usd=Decimal("0.010000"),
        worst_case_cost_usd=Decimal("0.030000"),
    )


class StorageEfficiencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_json_read_uses_one_download_without_a_head_request(self) -> None:
        backend = CountingBackend()
        storage = DaraStorage(backend)
        record = run_record()
        backend.objects[live_run_key("demo", record.job_id)] = json.dumps(
            record.model_dump(mode="json")
        ).encode()

        restored = storage.get_json(
            live_run_key("demo", record.job_id),
            LiveRunRecord,
        )

        self.assertIsNotNone(restored)
        self.assertEqual(backend.get_calls, 1)
        self.assertEqual(backend.exists_calls, 0)

    async def test_live_run_list_reuses_the_process_cache(self) -> None:
        backend = CountingBackend()
        storage = DaraStorage(backend)
        record = run_record()
        storage.put_json(live_run_key("demo", record.job_id), record)
        store = B2LiveRunStore(storage)

        first = await store.list("demo")
        second = await store.list("demo")

        self.assertEqual([item.job_id for item in first], [record.job_id])
        self.assertEqual([item.job_id for item in second], [record.job_id])
        self.assertEqual(backend.get_calls, 1)
        self.assertEqual(backend.exists_calls, 0)


if __name__ == "__main__":
    unittest.main()
