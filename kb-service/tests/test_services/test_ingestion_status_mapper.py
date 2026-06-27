from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.services.ingestion.status_mapper import (
    default_stage_statuses,
    ingest_response,
    playbook_document_id_from_metadata,
)


@dataclass
class _Document:
    id: UUID
    status: str
    metadata_: dict


def test_ingest_response_maps_admin_identity() -> None:
    playbook_document_id = uuid4()
    response = ingest_response(
        kb_service_document_id=uuid4(),
        metadata={
            "source_type": "admin_upload",
            "playbook_document_id": str(playbook_document_id),
        },
        task_id="task-id",
        status_="pending",
    )

    assert response.source_type == "admin_upload"
    assert response.playbook_document_id == playbook_document_id
    assert response.conversation_id is None
    assert response.conversation_file_id is None


def test_ingest_response_maps_conversation_file_identity() -> None:
    conversation_id = uuid4()
    conversation_file_id = uuid4()
    response = ingest_response(
        kb_service_document_id=uuid4(),
        metadata={
            "source_type": "conversation_file",
            "conversation_id": str(conversation_id),
            "conversation_file_id": str(conversation_file_id),
        },
        task_id="task-id",
        status_="pending",
    )

    assert response.source_type == "conversation_file"
    assert response.playbook_document_id is None
    assert response.conversation_id == conversation_id
    assert response.conversation_file_id == conversation_file_id


def test_default_stage_statuses_keep_contract_order() -> None:
    assert [stage.stage for stage in default_stage_statuses()] == [
        "parse",
        "chunk",
        "summarize",
        "embed",
        "load_vector",
    ]


def test_playbook_document_id_from_metadata_ignores_invalid_values() -> None:
    assert playbook_document_id_from_metadata({"playbook_document_id": "not-a-uuid"}) is None
