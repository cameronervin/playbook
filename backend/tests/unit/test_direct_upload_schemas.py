"""Schema tests for direct-upload request contracts."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.conversations import (
    ConversationFileSummaryResponse,
    ConversationFileUploadRequest,
    ConversationFileUploadRequestResponse,
)
from app.schemas.kb_documents import (
    KBDocumentResponse,
    KBDocumentStatus,
    KBDocumentUploadRequest,
    KBDocumentUploadRequestResponse,
)
from app.schemas.uploads import DirectUploadContract, UploadCompleteRequest


def test_direct_upload_contract_uses_upload_request_terminology() -> None:
    upload_request_id = uuid4()
    contract = DirectUploadContract(
        upload_request_id=upload_request_id,
        url="https://storage.example/upload",
        fields={"key": "kb/originals/document.pdf"},
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    completion = UploadCompleteRequest(upload_request_id=upload_request_id)

    assert contract.method == "POST"
    assert contract.upload_request_id == upload_request_id
    assert completion.upload_request_id == upload_request_id
    assert "upload_intent" not in str(contract.model_dump())


@pytest.mark.parametrize(
    "schema_cls",
    [KBDocumentUploadRequest, ConversationFileUploadRequest],
)
def test_upload_request_metadata_rejects_non_positive_size(schema_cls) -> None:
    with pytest.raises(ValidationError):
        schema_cls(
            filename="contract.pdf",
            content_type="application/pdf",
            size_bytes=0,
        )


def test_direct_upload_response_shape_keeps_storage_internals_out() -> None:
    now = datetime.now(UTC)
    contract = DirectUploadContract(
        upload_request_id=uuid4(),
        url="https://storage.example/upload",
        fields={"key": "conversation-files/originals/file.pdf"},
        expires_at=now + timedelta(minutes=10),
    )
    file_response = ConversationFileSummaryResponse(
        id=uuid4(),
        conversation_id=uuid4(),
        message_id=None,
        filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=123,
        extraction_status="upload_pending",
        chunk_count=0,
        created_at=now,
        updated_at=now,
    )
    response = ConversationFileUploadRequestResponse(
        file=file_response,
        upload=contract,
    )

    dumped = response.model_dump()

    assert dumped["upload"]["upload_request_id"] == contract.upload_request_id
    assert "storage_key" not in dumped["file"]
    assert "source_uri" not in dumped["file"]


def test_kb_document_upload_request_response_is_safe() -> None:
    now = datetime.now(UTC)
    document = KBDocumentResponse(
        id=uuid4(),
        organization_id=uuid4(),
        uploaded_by=uuid4(),
        title="NIL Handbook",
        filename="nil-handbook.pdf",
        content_type="application/pdf",
        size_bytes=456,
        processing_status="upload_pending",
        visibility_policy={"scope": "all_athletes"},
        metadata_tags={"topic": "nil"},
        kb_service_document_id=None,
        created_at=now,
        updated_at=now,
    )
    contract = DirectUploadContract(
        upload_request_id=uuid4(),
        url="https://storage.example/upload",
        fields={"key": "kb/originals/nil-handbook.pdf"},
        expires_at=now + timedelta(minutes=10),
    )

    response = KBDocumentUploadRequestResponse(document=document, upload=contract)

    assert response.document.processing_status == "upload_pending"
    assert "upload_pending" in KBDocumentStatus.__args__
    assert "storage_key" not in response.document.model_dump()
