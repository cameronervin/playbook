"""Code-based LangGraph eval harness for the agent layer.

Runs Langfuse-tracked evaluations over the project's agent chains and scores
them with two interchangeable judge backends — a custom LLM-as-judge and Ragas
(for RAG retrieval/generation metrics). Datasets and rubrics live on disk as
YAML and are mirrored into Langfuse via an idempotent sync.

Entry point: ``python -m evals.cli`` (run from the ``backend/`` directory).
See ``README.md`` for the full guide.
"""
