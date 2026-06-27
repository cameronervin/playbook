"""Run-scoped dependency containers for compiled agent graphs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.infrastructure.knowledgebase.providers.base import BaseKnowledgebaseProvider
from app.services.agent_stream_service import AgentStreamService


@dataclass(slots=True)
class AthleteChatRuntimeContext:
    """Dependencies that must be isolated per athlete chat invocation."""

    session: AsyncSession
    settings: Settings
    knowledgebase_provider: BaseKnowledgebaseProvider
    stream_service: AgentStreamService
    source_registry: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConversationTitleRuntimeContext:
    """Dependencies that must be isolated per title-generation invocation."""

    session: AsyncSession
    settings: Settings
