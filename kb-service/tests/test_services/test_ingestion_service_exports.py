from __future__ import annotations

import app.services.ingestion as facade


def test_ingestion_package_keeps_route_facing_facade_and_helper_aliases() -> None:
    assert facade.IngestionService is not None
    assert facade._metadata_from_ingest_request is facade.metadata_from_ingest_request
    assert facade._metadata_with_organization is facade.metadata_with_organization
    assert facade._dedupe_md5_for_ingest_request is facade.dedupe_md5_for_ingest_request
