"""Shared FastAPI dependencies for v1 routers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    current_active_user,
    require_admin,
    require_athlete,
    require_super_admin,
)
from app.core.config import Settings, get_request_settings
from app.infrastructure.db.session import get_db
from app.infrastructure.knowledgebase import (
    BaseKnowledgebaseProvider,
    get_kb_provider_dependency,
)
from app.infrastructure.storage import StorageProvider, get_storage_provider_dependency
from app.infrastructure.streaming import (
    BaseAgentStreamProvider,
    get_agent_stream_provider_dependency,
)
from app.models.identity import User
from app.services.agent_stream_service import AgentStreamService
from app.services.audit_service import AuditLogService
from app.services.auth_service import AuthService
from app.services.conversations import ConversationService
from app.services.kb_documents import (
    KBDocumentService,
    KBDocumentWebhookService,
)
from app.services.user_service import UserAdminService, UserProfileService

SessionDep = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_request_settings)]
CurrentUserDep = Annotated[User, Depends(current_active_user)]
AthleteUserDep = Annotated[User, Depends(require_athlete)]
AdminUserDep = Annotated[User, Depends(require_admin)]
SuperAdminUserDep = Annotated[User, Depends(require_super_admin)]
StorageProviderDep = Annotated[
    StorageProvider,
    Depends(get_storage_provider_dependency),
]
KBProviderDep = Annotated[
    BaseKnowledgebaseProvider,
    Depends(get_kb_provider_dependency),
]
AgentStreamProviderDep = Annotated[
    BaseAgentStreamProvider,
    Depends(get_agent_stream_provider_dependency),
]


def get_auth_service(session: SessionDep, settings: SettingsDep) -> AuthService:
    """Return auth service dependency."""
    return AuthService(session, settings=settings)


def get_user_profile_service(session: SessionDep) -> UserProfileService:
    """Return user profile service dependency."""
    return UserProfileService(session)


def get_user_admin_service(session: SessionDep) -> UserAdminService:
    """Return user-admin service dependency."""
    return UserAdminService(session)


def get_audit_service(session: SessionDep) -> AuditLogService:
    """Return audit service dependency."""
    return AuditLogService(session)


def get_conversation_service(session: SessionDep) -> ConversationService:
    """Return conversation service dependency."""
    return ConversationService(session)


def get_conversation_file_upload_service(
    session: SessionDep,
    storage: StorageProviderDep,
    settings: SettingsDep,
    kb_provider: KBProviderDep,
) -> ConversationService:
    """Return conversation service dependency for file-upload operations."""
    return ConversationService(
        session,
        storage=storage,
        settings=settings,
        kb_provider=kb_provider,
    )


def get_agent_stream_service(
    provider: AgentStreamProviderDep,
) -> AgentStreamService:
    """Return agent stream service dependency."""
    return AgentStreamService(provider)


def get_kb_document_service(
    session: SessionDep,
    storage: StorageProviderDep,
    kb_provider: KBProviderDep,
    settings: SettingsDep,
) -> KBDocumentService:
    """Return KB document service dependency."""
    return KBDocumentService(
        session,
        storage=storage,
        kb_provider=kb_provider,
        settings=settings,
    )


def get_kb_webhook_service(
    session: SessionDep,
    settings: SettingsDep,
) -> KBDocumentWebhookService:
    """Return KB webhook service dependency."""
    return KBDocumentWebhookService(session, settings=settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
UserProfileServiceDep = Annotated[
    UserProfileService,
    Depends(get_user_profile_service),
]
UserAdminServiceDep = Annotated[UserAdminService, Depends(get_user_admin_service)]
AuditLogServiceDep = Annotated[AuditLogService, Depends(get_audit_service)]
ConversationServiceDep = Annotated[
    ConversationService,
    Depends(get_conversation_service),
]
ConversationFileUploadServiceDep = Annotated[
    ConversationService,
    Depends(get_conversation_file_upload_service),
]
AgentStreamServiceDep = Annotated[
    AgentStreamService,
    Depends(get_agent_stream_service),
]
KBDocumentServiceDep = Annotated[
    KBDocumentService,
    Depends(get_kb_document_service),
]
KBDocumentWebhookServiceDep = Annotated[
    KBDocumentWebhookService,
    Depends(get_kb_webhook_service),
]
