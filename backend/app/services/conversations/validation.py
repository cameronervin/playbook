"""Validation helpers for athlete conversation services."""

from __future__ import annotations

from uuid import UUID

from app.core.exceptions import ValidationError
from app.repositories.conversations import (
    ConversationFileRepository,
    ConversationMessageRepository,
)


async def validate_attached_files(
    *,
    file_repo: ConversationFileRepository,
    conversation_id: UUID,
    file_ids: list[UUID],
) -> None:
    """Ensure requested file IDs are scoped to the conversation."""
    if not file_ids:
        return

    files = await file_repo.list_by_conversation_and_ids(conversation_id, file_ids)
    if {file.id for file in files} != set(file_ids):
        raise ValidationError(
            "One or more file_ids are not available for this conversation"
        )


async def validate_message_attachment(
    *,
    message_repo: ConversationMessageRepository,
    conversation_id: UUID,
    message_id: UUID | None,
) -> None:
    """Ensure an optional attachment target message is in the conversation."""
    if message_id is None:
        return

    message = await message_repo.get(message_id)
    if message is None or message.conversation_id != conversation_id:
        raise ValidationError("message_id is not available for this conversation")
