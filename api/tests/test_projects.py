from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import dara.main as main_module
from dara.projects import MemoryProjectStore


class ProjectEndpointTests(unittest.TestCase):
    def test_project_crud_is_b2_store_shaped_and_policy_validated(self) -> None:
        store = MemoryProjectStore()
        actor = "anon_" + "7" * 32
        with (
            patch.object(main_module, "project_store", store),
            patch.object(
                main_module,
                "public_action_rate_limiter",
                main_module.PublicActionRateLimiter(),
            ),
            patch.dict("os.environ", {"DARA_API_TOKEN": "test-token"}),
            TestClient(main_module.app) as client,
        ):
            created = client.post(
                "/v1/projects",
                headers={
                    "Authorization": "Bearer test-token",
                    "X-Dara-Actor": actor,
                },
                json={
                    "name": "Acme — Launch",
                    "client": "Acme",
                    "policy_id": "pol_standard",
                    "tags": ["launch"],
                },
            )
            project_id = created.json()["project_id"]
            read = client.get(
                f"/v1/projects/{project_id}",
                headers={"Authorization": "Bearer test-token"},
            )
            updated = client.put(
                f"/v1/projects/{project_id}",
                headers={
                    "Authorization": "Bearer test-token",
                    "X-Dara-Actor": actor,
                },
                json={
                    "name": "Acme — Fall launch",
                    "client": "Acme",
                    "policy_id": "pol_locked",
                    "tags": ["launch", "fall"],
                },
            )
            listed = client.get(
                "/v1/projects",
                headers={"Authorization": "Bearer test-token"},
            )

        self.assertEqual(created.status_code, 201)
        self.assertRegex(project_id, r"^prj_[0-9A-HJKMNP-TV-Z]{26}$")
        self.assertEqual(read.json()["name"], "Acme — Launch")
        self.assertEqual(updated.json()["policy_id"], "pol_locked")
        self.assertIn(project_id, [item["project_id"] for item in listed.json()["items"]])

    def test_project_mutation_rejects_unknown_policy(self) -> None:
        with (
            patch.object(main_module, "project_store", MemoryProjectStore()),
            patch.dict("os.environ", {"DARA_API_TOKEN": "test-token"}),
            TestClient(main_module.app) as client,
        ):
            response = client.post(
                "/v1/projects",
                headers={"Authorization": "Bearer test-token"},
                json={
                    "name": "Acme — Launch",
                    "client": "Acme",
                    "policy_id": "pol_missing",
                },
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "POLICY_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
