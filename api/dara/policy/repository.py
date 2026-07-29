from __future__ import annotations

import asyncio
from typing import Protocol

from ..storage import DaraStorage
from .models import JobRecord, Policy


class JobStore(Protocol):
    async def put_job(self, job: JobRecord) -> None: ...

    async def get_job(self, tenant_id: str, job_id: str) -> JobRecord | None: ...


class MemoryJobStore:
    def __init__(self) -> None:
        self.jobs: dict[str, JobRecord] = {}

    async def put_job(self, job: JobRecord) -> None:
        self.jobs[job.job_id] = job.model_copy(deep=True)

    async def get_job(self, tenant_id: str, job_id: str) -> JobRecord | None:
        job = self.jobs.get(job_id)
        if job is None or job.tenant_id != tenant_id:
            return None
        return job.model_copy(deep=True)


def job_storage_key(tenant_id: str, job_id: str) -> str:
    return f"dara/state/jobs/{tenant_id}/{job_id}.json"


class B2JobStore:
    def __init__(self, storage: DaraStorage) -> None:
        self.storage = storage

    async def put_job(self, job: JobRecord) -> None:
        await asyncio.to_thread(
            self.storage.put_json,
            job_storage_key(job.tenant_id, job.job_id),
            job,
        )

    async def get_job(self, tenant_id: str, job_id: str) -> JobRecord | None:
        return await asyncio.to_thread(
            self.storage.get_json,
            job_storage_key(tenant_id, job_id),
            JobRecord,
        )


class PolicyStore(Protocol):
    async def put_policy(self, policy: Policy) -> None: ...

    async def get_policy(self, tenant_id: str, policy_id: str) -> Policy | None: ...

    async def list_policies(self, tenant_id: str) -> list[Policy]: ...


class MemoryPolicyStore:
    def __init__(self, policies: tuple[Policy, ...] = ()) -> None:
        self.policies = {policy.policy_id: policy for policy in policies}

    async def put_policy(self, policy: Policy) -> None:
        self.policies[policy.policy_id] = policy

    async def get_policy(self, tenant_id: str, policy_id: str) -> Policy | None:
        policy = self.policies.get(policy_id)
        return policy if policy is not None and policy.tenant_id == tenant_id else None

    async def list_policies(self, tenant_id: str) -> list[Policy]:
        return sorted(
            (
                policy
                for policy in self.policies.values()
                if policy.tenant_id == tenant_id
            ),
            key=lambda policy: policy.policy_id,
        )


def policy_storage_key(tenant_id: str, policy_id: str) -> str:
    return f"dara/state/policies/{tenant_id}/{policy_id}.json"


class B2PolicyStore:
    def __init__(self, storage: DaraStorage) -> None:
        self.storage = storage

    async def put_policy(self, policy: Policy) -> None:
        await asyncio.to_thread(
            self.storage.put_json,
            policy_storage_key(policy.tenant_id, policy.policy_id),
            policy,
        )

    async def get_policy(self, tenant_id: str, policy_id: str) -> Policy | None:
        return await asyncio.to_thread(
            self.storage.get_json,
            policy_storage_key(tenant_id, policy_id),
            Policy,
        )

    async def list_policies(self, tenant_id: str) -> list[Policy]:
        prefix = f"dara/state/policies/{tenant_id}/"
        keys = await asyncio.to_thread(self.storage.list_prefix, prefix)
        values = await asyncio.gather(
            *(
                asyncio.to_thread(self.storage.get_json, key, Policy)
                for key in keys
            )
        )
        return sorted(
            (policy for policy in values if policy is not None),
            key=lambda policy: policy.policy_id,
        )
