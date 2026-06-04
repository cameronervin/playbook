"""Smoke tests for infrastructure database exports."""


def test_database_session_helpers_import_from_infrastructure() -> None:
    from app.infrastructure.db.session import cleanup_db_engine, get_db, get_session_factory

    assert callable(cleanup_db_engine)
    assert callable(get_db)
    assert callable(get_session_factory)
