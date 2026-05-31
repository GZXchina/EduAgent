from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.deps import get_db
from database.repository import ResourceRepository

router = APIRouter(prefix="/api/resources", tags=["resources"])


class ResourceItem(BaseModel):
    id: int
    session_id: str
    resource_type: str
    content: dict[str, Any]
    created_at: str | None = None


class ResourceListResponse(BaseModel):
    session_id: str
    resources: list[ResourceItem]


class ResourceTypeResponse(BaseModel):
    session_id: str
    resource_type: str
    resources: list[ResourceItem]


@router.get("/{session_id}", response_model=ResourceListResponse)
async def get_resources_by_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> ResourceListResponse:
    repo = ResourceRepository(db)
    rows = repo.get_resources_by_session(session_id)
    resources = [
        ResourceItem(
            id=row.id,
            session_id=row.session_id,
            resource_type=row.resource_type,
            content=ResourceRepository.resource_to_dict(row),
            created_at=row.created_at.isoformat() if row.created_at else None,
        )
        for row in rows
    ]
    return ResourceListResponse(session_id=session_id, resources=resources)


@router.get("/{session_id}/{resource_type}", response_model=ResourceTypeResponse)
async def get_resources_by_type(
    session_id: str,
    resource_type: str,
    db: Session = Depends(get_db),
) -> ResourceTypeResponse:
    repo = ResourceRepository(db)
    rows = repo.get_resources_by_type(session_id, resource_type)
    resources = [
        ResourceItem(
            id=row.id,
            session_id=row.session_id,
            resource_type=row.resource_type,
            content=ResourceRepository.resource_to_dict(row),
            created_at=row.created_at.isoformat() if row.created_at else None,
        )
        for row in rows
    ]
    return ResourceTypeResponse(
        session_id=session_id,
        resource_type=resource_type,
        resources=resources,
    )
