from __future__ import annotations

from app.models.document import Document
from app.schemas.status import DocumentStatusResponse


def test_document_model_has_nullable_summary_column() -> None:
    column = Document.__table__.c.summary

    assert column.nullable is True
    assert str(column.type) == "TEXT"


def test_document_status_response_includes_summary() -> None:
    response = DocumentStatusResponse(
        kb_service_document_id="00000000-0000-0000-0000-000000000001",
        stages=[],
        summary="One-sentence orientation summary.",
    )

    assert response.summary == "One-sentence orientation summary."
