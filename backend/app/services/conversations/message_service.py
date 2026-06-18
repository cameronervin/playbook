"""Message submission and stream authorization workflows."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, NotFoundError
from app.models.identity import User
from app.repositories.conversations import (
    ConversationFileRepository,
    ConversationMessageRepository,
    ConversationRepository,
)
from app.schemas.conversations import MessageSubmitRequest, MessageSubmitResponse
from app.services.conversations.validation import validate_attached_files
from app.workers.dispatcher import AthleteChatTaskDispatcher, AthleteChatTaskPayload
from app.workers.queues import WorkerTaskName

logger = structlog.get_logger(__name__)


class ConversationMessageService:
    """Persist user turns, dispatch assistant work, and authorize streams."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        conversation_repo: ConversationRepository,
        message_repo: ConversationMessageRepository,
        file_repo: ConversationFileRepository,
        athlete_chat_dispatcher: AthleteChatTaskDispatcher,
    ) -> None:
        self.session = session
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
        self.file_repo = file_repo
        self.athlete_chat_dispatcher = athlete_chat_dispatcher

    async def submit_message(
        self,
        *,
        athlete: User,
        conversation_id: UUID,
        request: MessageSubmitRequest,
    ) -> MessageSubmitResponse:
        """Persist a user turn, enqueue assistant work, and return stream metadata."""
        conversation = await self.conversation_repo.get_for_athlete(
            conversation_id=conversation_id,
            organization_id=athlete.organization_id,
            athlete_id=athlete.id,
        )
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))

        await validate_attached_files(
            file_repo=self.file_repo,
            conversation_id=conversation.id,
            file_ids=request.file_ids,
        )

        attached_file_ids = [str(file_id) for file_id in request.file_ids]
        task_id = str(uuid4())
        user_message = await self.message_repo.create(
            conversation_id=conversation.id,
            role="user",
            content=request.content,
            status="complete",
            metadata={"attached_file_ids": attached_file_ids},
        )
        assistant_message = await self.message_repo.create(
            conversation_id=conversation.id,
            role="assistant",
            content="",
            status="streaming",
            created_at=user_message.created_at + timedelta(microseconds=1),
            metadata={
                "task_id": task_id,
                "task_name": WorkerTaskName.RUN_ATHLETE_CHAT.value,
                "user_message_id": str(user_message.id),
            },
        )
        await self.conversation_repo.update_last_message_at(
            conversation,
            last_message_at=user_message.created_at,
        )
        await self.session.commit()

        try:
            self.athlete_chat_dispatcher.dispatch(
                task_id=task_id,
                payload=AthleteChatTaskPayload(
                    conversation_id=conversation.id,
                    athlete_user_id=athlete.id,
                    user_message_id=user_message.id,
                    assistant_message_id=assistant_message.id,
                    organization_id=athlete.organization_id,
                    attached_file_ids=request.file_ids,
                ),
            )
        except Exception as exc:
            await self.message_repo.update_status_and_content(
                assistant_message,
                status="failed",
                metadata={
                    **assistant_message.message_metadata,
                    "dispatch_error": type(exc).__name__,
                },
            )
            await self.session.commit()
            logger.error(
                "athlete_chat_task_dispatch_failed",
                conversation_id=str(conversation.id),
                assistant_message_id=str(assistant_message.id),
                task_id=task_id,
                error_type=type(exc).__name__,
                exc_info=True,
            )
            raise AppError(
                "Failed to enqueue athlete chat task",
                ErrorCode.AGENT_FAILED,
                retryable=True,
                details={
                    "conversation_id": str(conversation.id),
                    "assistant_message_id": str(assistant_message.id),
                },
            ) from exc

        return MessageSubmitResponse(
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            task_id=task_id,
            stream_url=(
                f"/api/v1/conversations/{conversation.id}/messages/"
                f"{assistant_message.id}/stream?task_id={task_id}"
            ),
            status=assistant_message.status,
        )

    async def validate_message_stream(
        self,
        *,
        athlete: User,
        conversation_id: UUID,
        message_id: UUID,
        task_id: str,
    ) -> None:
        """Validate that an athlete can subscribe to one assistant message stream."""
        conversation = await self.conversation_repo.get_for_athlete(
            conversation_id=conversation_id,
            organization_id=athlete.organization_id,
            athlete_id=athlete.id,
        )
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))

        message = await self.message_repo.get(message_id)
        if (
            message is None
            or message.conversation_id != conversation.id
            or message.role != "assistant"
            or message.message_metadata.get("task_id") != task_id
        ):
            raise NotFoundError("Message stream", str(message_id))
