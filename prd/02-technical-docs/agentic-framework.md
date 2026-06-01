# Agentic Framework

> Defines the agent runtime: how LLM work is structured and run. The framework
> is built on LangGraph + LangChain with an Anthropic-first provider layer. This
> is a generic template — adapt the steps and schemas to your product.

## Building Blocks

| Concept | Responsibility |
|---------|----------------|
| **Chain** | A single LLM unit of work: a prompt + model + (optional) tools + structured output schema. Built with LangChain's `create_agent`. |
| **Node** | A step in a graph. May be a chain invocation or deterministic logic (load state, save state, route, validate). |
| **Graph** | A LangGraph state machine wiring nodes together with edges/conditions. |
| **Executor** | Runs/resumes a graph for a given input, manages checkpoints, and surfaces results. |
| **Tool** | A typed callable the model can invoke mid-run (see `docs/agents/tools.md`). |

```
Executor ──runs──► Graph ──contains──► Nodes ──invoke──► Chains ──may use──► Tools
                                  │
                                  └── deterministic nodes (load/save/route/validate)
```

## Runtime

- All graphs use a **PostgreSQL-backed checkpointer**, so a long run can resume
  by `thread_id` after a crash or restart.
- The LLM is obtained through `BaseLLMProvider.get_chat_model()`. Transport
  (`direct` vs `gateway`) follows `LLM_PROVIDER_MODE` config — the framework is
  vendor-agnostic. Default is Anthropic via `direct`.
- Long-running runs may be executed inline (request/response or streamed) or
  offloaded to a Celery worker and polled.

## Example Flow: Generate Example Content (US-03)

```
input prompt
     │
     ▼
[load_state node]  ── read the Example and any prior data
     │
     ▼
[generate node]    ── invoke the generation chain (prompt + model + schema)
     │
     ▼
[validate node]    ── check structured output against the schema
     │
     ▼
[save_state node]  ── persist generated content onto Example.data
     │
     ▼
result
```

### Chain Definition

```python
from langchain.agents import create_agent
from app.agents.prompts.generate import GENERATE_PROMPT
from app.agents.schemas import GeneratedContent


def create_generate_chain(chat_model):
    return create_agent(
        model=chat_model,
        system_prompt=GENERATE_PROMPT,
        response_format=GeneratedContent,   # structured output
    )
```

### Structured Output

Chains that produce data return a typed schema, not free text:

```json
{
  "title": "string",
  "body": "string",
  "tags": ["string"]
}
```

The `validate` node rejects malformed output and triggers a bounded retry before
failing the run.

## Context Engineering

What each step receives is governed by a policy-driven middleware layer
(serializers + policies + a middleware factory). See
`docs/agents/context-engineering.md`. Prefer compact, retrieval-style context
over loading whole records.

## Safety and Validation Gates

1. Structured outputs are schema-validated at node boundaries; invalid output
   triggers a bounded repair/retry, then a clean failure.
2. Tool inputs/outputs are typed; tools never receive unvalidated free-form
   instructions from untrusted content.
3. Runs that fail leave no partial persisted state (write only on success).
4. Per-step context limits and truncation policy are enforced.

## Token Efficiency and Prompt Caching

1. Track token usage per step and per run.
2. Keep a stable prompt prefix (instructions + schema) and append dynamic
   context at the end to maximize cache reuse.
3. Version the cacheable prefix (e.g. `prompt_version`) so changes invalidate
   stale cache entries deterministically.
4. Validate provider/transport caching compatibility before enabling it in
   production.

## Observability

- Track run duration, status transitions, and failure reasons per graph.
- Track token usage per step and per run.
- Log at node boundaries with structured context (run id, step, status).

## Failure and Recovery

1. Failed runs preserve their run record and expose a retry path.
2. Partial outputs are marked and never treated as complete.
3. Checkpointing lets interrupted runs resume by `thread_id`.

## File Layout

```
backend/app/agents/
├── chains/      # per-task chains (create_agent)
├── nodes/       # graph nodes (chain calls + deterministic steps)
├── graphs/      # graph assembly
├── executors/   # run/resume graphs, manage checkpoints
├── context/     # policies, serializers, middleware
├── prompts/     # task prompts
└── tools/       # agent tools
```
