"""Pydantic schemas for document status contract endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class StageStatus(BaseModel):
    stage: str
    status: str | None
    task_id: str | None


class TaskStatusResponse(BaseModel):
    task_id: str
    document_id: uuid.UUID | None
    celery_state: str | None
    stages: list[StageStatus]
    error_message: str | None = None
    updated_at: datetime | None = None


class DocumentStatusResponse(BaseModel):
    kb_service_document_id: uuid.UUID
    playbook_document_id: uuid.UUID | None = None
    task_id: str | None = None
    status: str | None = None
    stages: list[StageStatus]
    error_message: str | None = None
    updated_at: datetime | None = None
