# Context Engineering

> How to control what each agent step receives, to reduce token usage, improve
> focus, and lower cost. Athlete chat currently uses dedicated LangChain
> middleware that preserves bounded history and appends compact runtime flags.
> The policy/serializer utilities remain available for future workflows that
> need declarative context injection.

## Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Context Engineering Flow                         │
│                                                                      │
│  ┌──────────────┐     ┌───────────────────┐     ┌────────────────┐  │
│  │ Graph State  │────►│ Athlete Middleware │────►│  Guardrails    │  │
│  │ load_state   │     │ athlete_chat_...py │     │ guardrails/    │  │
│  └──────────────┘     └───────────────────┘     └────────────────┘  │
│         │                      │                        │            │
│         │                      ▼                        │            │
│         │            ┌─────────────────┐               │            │
│         └───────────►│ runtime context │◄──────────────┘            │
│                      │   (middleware)  │                             │
│                      └────────┬────────┘                             │
│                               ▼                                      │
│                      ┌─────────────────┐                             │
│                      │  context message │                            │
│                      │  appended to req │                            │
│                      └─────────────────┘                             │
└─────────────────────────────────────────────────────────────────────┘
```

Three active components:

1. **Graph state** — bounded messages and JSON-safe runtime fields loaded by graph nodes.
2. **Middleware** — filters message noise, enforces loop guardrails, and appends compact flags.
3. **Deterministic scope nodes** — prepare trusted private scope that the model
   must not choose for itself.
4. **Tools** — retrieve large, authoritative, or private context just in time.

## 1. Athlete Middleware

Athlete chat uses `create_athlete_chat_middleware()` in the nested
`create_agent(...)` chain. The middleware:

- keeps the bounded prior conversation history loaded by `load_state`;
- drops blank human/AI messages while preserving system messages, AI tool calls,
  and tool results;
- applies `assert_message_loop_bounded(...)`;
- appends compact runtime context: current question, KB-support flag,
  topic/risk labels, attached-file IDs/count, and ready-file count;
- appends a bounded uploaded-file manifest when ready conversation files have
  summaries or file metadata available.

It must not inject KB search results, extracted uploaded-file text, secrets, or
citation metadata. The model gets official shared guidance through
`search_playbook_knowledgebase`, private uploaded-file snippets through
`search_conversation_files`, and file-level summaries through the manifest for
orientation only. `save_state` validates/persists citations.

## 2. Conversation-File Scope Preparation

Athlete chat runs `prepare_conversation_file_scope` after deterministic safety
checks and before model generation. The graph node:

- skips safety-bypass turns;
- selects only `conversation_files` rows with `extraction_status="ready"` and
  `chunk_count > 0`;
- narrows to attached `file_ids` when present, otherwise searches all ready
  files in the conversation;
- stores selected ready file IDs in graph state for hidden tool scope;
- stores a compact uploaded-file manifest in graph state for middleware
  injection.

The `run_agent` node binds `organization_id`, `conversation_id`, and selected
ready file IDs into hidden context for `search_conversation_files`. The model can
decide when to search uploaded files and what query terms to use, but it cannot
choose private scope, source type, conversation ID, or arbitrary file filters.
Returned chunks are registered in the same source registry used by
`search_playbook_knowledgebase`. The uploaded-file manifest is not evidence and
must not be cited; only retrieved chunk excerpts returned by
`search_conversation_files` are supporting evidence.

The model never receives whole uploaded documents, storage keys, signed URLs, or
raw extracted-text artifacts.

## 3. Policy Utilities

For future workflows, a policy can be the single source of truth for what
context a step gets. `policies.py` defines `ContextField` and
`PhaseContextPolicy`; the registry is intentionally empty until another
workflow needs declarative context injection.

## 4. Serializers

Serializers turn state objects into text at a chosen level of detail. Use tiers
to spend tokens only where they matter.

| Tier | Token usage | Purpose |
|------|-------------|---------|
| `compact` | ~30% of JSON | High-level structure only |
| `full` | ~60% of JSON | Complete data, formatted as text |
| `json` | 100% | Raw JSON (e.g. for edit/re-run scenarios) |

```python
SERIALIZER_REGISTRY = {
    ("input_data", "compact"): serialize_input_compact,
    ("input_data", "full"): serialize_input_full,
}


def get_serializer(field_name: str, tier: str):
    if tier == "json":
        return serialize_to_json
    return SERIALIZER_REGISTRY[(field_name, tier)]
```

## Token Budgeting

- Track token usage per step and per run.
- Enforce per-step context limits and a truncation policy.
- Prefer retrieval **snippets** over loading whole documents.
- Drop to `compact` tiers for steps that only need structure.

## Prompt Composition

- Keep a **stable prefix** (instructions, schema, policy) at the front and
  append dynamic per-run context at the end. This maximizes cache reuse and
  keeps the model's instructions consistent.
- Put instructions in the **system prompt**; put data in the **injected context
  message**. Don't mix the two.
- For athlete chat, conversation history is loaded by
  `load_state` and passed as bounded LangChain messages. The athlete-specific
  middleware preserves that history, filters blank message entries, applies the
  message-loop guard, and appends a compact runtime context with the current
  question, KB-support flag, labels, attached-file IDs/count, and ready-file
  count. It may append a bounded uploaded-file manifest for orientation. Shared
  KB context is loaded just-in-time through `search_playbook_knowledgebase`.
  Uploaded-file evidence is loaded just-in-time through
  `search_conversation_files`, using private scope prepared deterministically by
  the graph. Citation metadata is captured from registered sources rather than
  injected wholesale.

## Prompt Caching

- A stable prefix is a prerequisite for provider prompt caching — order matters.
- Version the cacheable prefix (e.g. a `prompt_version` / `policy_version`) so a
  prompt change invalidates stale cache entries deterministically.
- Validate provider/transport compatibility (direct vs gateway) before relying
  on caching in production — caching headers and semantics can differ.

## Design Rationale

- **Single source of truth** — editing a policy changes runtime behavior; no
  duplicated middleware.
- **Declarative** — easy to audit exactly what each step receives.
- **Token efficient** — tiered serialization saves 50–80% on later steps.
- **Composable** — middleware combines cleanly with other middleware and has
  full access to graph state.

## File Structure

```
backend/app/agents/context/
├── __init__.py
├── policies.py       # ContextField, StepContextPolicy, CONTEXT_POLICIES
├── serializers.py    # serializers + SERIALIZER_REGISTRY
└── middleware/
    └── athlete_chat_middleware.py
```
