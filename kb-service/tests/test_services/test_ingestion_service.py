from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.ingestion_service import _metadata_with_organization


def test_metadata_with_organization_stamps_missing_scope() -> None:
    organization_id = uuid4()

    metadata = _metadata_with_organization(
        {"source_title": "NIL Handbook"},
        organization_id=organization_id,
    )

    assert metadata["organization_id"] == str(organization_id)
    assert metadata["source_title"] == "NIL Handbook"


def test_metadata_with_organization_rejects_conflicting_scope() -> None:
    organization_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        _metadata_with_organization(
            {"organization_id": str(uuid4())},
            organization_id=organization_id,
        )

    assert exc_info.value.status_code == 400
    assert "organization_id" in str(exc_info.value.detail)
