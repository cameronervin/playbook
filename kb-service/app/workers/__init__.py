"""Celery worker package — the ingest pipeline (parse → chunk → embed → load_vector).

Importing this package does NOT require a running broker: the Celery app is
constructed with broker/backend URLs from settings but no connection is opened
until a task is dispatched or a worker boots. See ``app.py`` for the app object
and ``tasks.py`` for the pipeline tasks.
"""
from __future__ import annotations
