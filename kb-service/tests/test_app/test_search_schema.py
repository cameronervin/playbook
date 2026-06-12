from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.search import SearchRequest


def test_search_request_requires_organization_id() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(
            query="nil disclosure",
            configuration_id=uuid4(),
            max_docs=10,
            score_threshold=0.7,
        )


def test_search_request_accepts_organization_id() -> None:
    organization_id = uuid4()
    request = SearchRequest(
        query="nil disclosure",
        organization_id=organization_id,
        configuration_id=uuid4(),
        max_docs=10,
        score_threshold=0.7,
    )

    assert request.organization_id == organization_id
