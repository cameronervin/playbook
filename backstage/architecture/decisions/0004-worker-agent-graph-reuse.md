# ADR 0004 — Worker Agent Graph Reuse

## Status

Accepted

## Context

Athlete chat worker tasks previously rebuilt LangGraph graphs for each task.
Local measurement showed graph construction was small relative to model latency,
but still measurable on the worker hot path. The old graph factories also closed
over per-task objects such as SQLAlchemy sessions, stream services, and mutable
KB citation registries, which made direct singleton reuse unsafe.

## Decision

Worker agent graphs are compiled as process-local reusable objects through an
`AgentGraphProviderCache` and lazily materialized `AgentGraphProvider`. The
compiled graph topology, chains, tools, and checkpointer are static for the
worker process.

Per-run dependencies are passed with LangGraph/LangChain runtime context:

- DB session and repositories are resolved during node execution.
- Stream service, settings, KB provider, and citation source registry are scoped
  to one graph invocation.
- KB tools read provider and source registry only from `ToolRuntime.context`;
  they do not retain build-time provider or registry fallbacks.
- The worker owns a lazy process-lifetime LangGraph checkpointer so cached
  compiled graphs do not bind to per-task checkpointer instances.

## Consequences

**Positive**
- Avoids repeated graph compilation on every athlete chat and title task.
- Prevents DB sessions and mutable citation registries from leaking across tasks.
- Keeps model clients provider-cached through the existing LLM provider boundary.

**Negative**
- Runtime context is now part of the internal agent contract and must be supplied
  by executors and tests.
- Worker shutdown must close the process-lifetime checkpointer pool.

**Follow-ups**
- Apply the same provider/context pattern to future admin chat or dashboard
  insight agents before caching their graphs.
