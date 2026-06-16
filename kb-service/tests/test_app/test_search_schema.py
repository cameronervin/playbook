from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.search import SearchRequest


def test_search_request_requires_organization_id() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(
            query="nil disclosure",
            limit=10,
            score_threshold=0.7,
        )


def test_search_request_accepts_organization_id() -> None:
    organization_id = uuid4()
    request = SearchRequest(
        query="nil disclosure",
        organization_id=organization_id,
        visibility_context={"role": "athlete"},
        limit=10,
        score_threshold=0.7,
    )

    assert request.organization_id == organization_id
    assert request.visibility_context == {"role": "athlete"}
    assert request.limit == 10
    assert request.source_types == ["admin_upload"]
    assert request.conversation_id is None
    assert request.file_ids == []


def test_search_request_accepts_private_conversation_scope() -> None:
    organization_id = uuid4()
    conversation_id = uuid4()
    file_id = uuid4()

    request = SearchRequest(
        query="contract approval",
        organization_id=organization_id,
        source_types=["conversation_file"],
        conversation_id=conversation_id,
        file_ids=[file_id],
    )

    assert request.source_types == ["conversation_file"]
    assert request.conversation_id == conversation_id
    assert request.file_ids == [file_id]


def test_search_request_accepts_combined_shared_and_private_scope() -> None:
    conversation_id = uuid4()

    request = SearchRequest(
        query="nil contract approval",
        organization_id=uuid4(),
        source_types=["admin_upload", "conversation_file"],
        conversation_id=conversation_id,
    )

    assert request.source_types == ["admin_upload", "conversation_file"]
    assert request.conversation_id == conversation_id


def test_search_request_rejects_empty_or_duplicate_source_types() -> None:
    with pytest.raises(ValidationError, match="source_types"):
        SearchRequest(
            query="nil disclosure",
            organization_id=uuid4(),
            source_types=[],
        )

    with pytest.raises(ValidationError, match="source_types"):
        SearchRequest(
            query="nil disclosure",
            organization_id=uuid4(),
            source_types=["admin_upload", "admin_upload"],
        )


def test_search_request_requires_conversation_scope_for_private_search() -> None:
    with pytest.raises(ValidationError, match="conversation_id"):
        SearchRequest(
            query="contract approval",
            organization_id=uuid4(),
            source_types=["conversation_file"],
        )


def test_search_request_rejects_file_ids_without_private_search() -> None:
    with pytest.raises(ValidationError, match="file_ids"):
        SearchRequest(
            query="nil disclosure",
            organization_id=uuid4(),
            source_types=["admin_upload"],
            file_ids=[uuid4()],
        )
