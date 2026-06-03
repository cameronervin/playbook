"""Agent-agnostic eval core: types, rubrics, judges, sync, runner, aggregate.

``core/`` knows nothing about the project's specific agents (that lives in
``specs/``) and ``specs/`` know nothing about Langfuse plumbing. The one
exception is ``core/graph_env.py``, which is the single place that imports
``app.*`` to build the agent chains and the LiteLLM-gateway evaluator models.
"""
