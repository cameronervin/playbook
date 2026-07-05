from __future__ import annotations

import uuid

from sqlalchemy.dialects import postgresql

from app.repositories.document_repo import DocumentRepository


def test_admin_source_identity_statement_filters_jsonb_metadata() -> None:
    organization_id = uuid.uuid4()
    playbook_document_id = uuid.uuid4()

    statement = DocumentRepository.admin_source_identity_statement(
        configuration_id=uuid.uuid4(),
        organization_id=organization_id,
        playbook_document_id=playbook_document_id,
    )

    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "kb.documents.metadata @>" in sql
    assert {
        "source_type": "admin_upload",
        "organization_id": str(organization_id),
        "playbook_document_id": str(playbook_document_id),
    } in compiled.params.values()


def test_conversation_file_source_identity_statement_filters_private_jsonb_metadata() -> None:
    organization_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    conversation_file_id = uuid.uuid4()

    statement = DocumentRepository.conversation_file_source_identity_statement(
        configuration_id=uuid.uuid4(),
        organization_id=organization_id,
        conversation_id=conversation_id,
        conversation_file_id=conversation_file_id,
    )

    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "kb.documents.metadata @>" in sql
    assert {
        "source_type": "conversation_file",
        "organization_id": str(organization_id),
        "conversation_id": str(conversation_id),
        "conversation_file_id": str(conversation_file_id),
        "visibility_policy": {"scope": "conversation"},
    } in compiled.params.values()
