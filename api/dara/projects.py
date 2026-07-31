from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from .storage import DaraStorage


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    project_id: str = Field(pattern=r"^prj_[A-Za-z0-9_-]{2,80}$")
    tenant_id: str = "demo"
    name: str = Field(min_length=2, max_length=120)
    client: str = Field(min_length=2, max_length=120)
    policy_id: str = Field(pattern=r"^pol_[a-z0-9_-]{2,64}$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tags: tuple[str, ...] = ()


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    client: str = Field(min_length=2, max_length=120)
    policy_id: str = Field(default="pol_standard", pattern=r"^pol_[a-z0-9_-]{2,64}$")
    tags: tuple[str, ...] = ()


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    client: str = Field(min_length=2, max_length=120)
    policy_id: str = Field(pattern=r"^pol_[a-z0-9_-]{2,64}$")
    tags: tuple[str, ...] = ()


class ProjectStore(Protocol):
    async def put(self, project: Project) -> None: ...

    async def get(self, tenant_id: str, project_id: str) -> Project | None: ...

    async def list(self, tenant_id: str) -> list[Project]: ...


def project_key(tenant_id: str, project_id: str) -> str:
    return f"dara/state/projects/{tenant_id}/{project_id}.json"


class MemoryProjectStore:
    def __init__(self, projects: tuple[Project, ...] = ()) -> None:
        self.projects = {project.project_id: project for project in projects}

    async def put(self, project: Project) -> None:
        self.projects[project.project_id] = project.model_copy(deep=True)

    async def get(self, tenant_id: str, project_id: str) -> Project | None:
        project = self.projects.get(project_id)
        if project is None or project.tenant_id != tenant_id:
            return None
        return project.model_copy(deep=True)

    async def list(self, tenant_id: str) -> list[Project]:
        return sorted(
            (
                project.model_copy(deep=True)
                for project in self.projects.values()
                if project.tenant_id == tenant_id
            ),
            key=lambda project: project.project_id,
        )


class B2ProjectStore:
    def __init__(self, storage: DaraStorage) -> None:
        self.storage = storage

    async def put(self, project: Project) -> None:
        await asyncio.to_thread(
            self.storage.put_json,
            project_key(project.tenant_id, project.project_id),
            project,
        )

    async def get(self, tenant_id: str, project_id: str) -> Project | None:
        return await asyncio.to_thread(
            self.storage.get_json,
            project_key(tenant_id, project_id),
            Project,
        )

    async def list(self, tenant_id: str) -> list[Project]:
        keys = await asyncio.to_thread(
            self.storage.list_prefix,
            f"dara/state/projects/{tenant_id}/",
        )
        values = await asyncio.gather(
            *(asyncio.to_thread(self.storage.get_json, key, Project) for key in keys)
        )
        return sorted(
            (project for project in values if project is not None),
            key=lambda project: project.project_id,
        )
