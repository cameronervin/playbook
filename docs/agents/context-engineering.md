# Context Engineering

> How to control what each agent step receives, to reduce token usage, improve
> focus, and lower cost. The pattern is **policy-driven**: declarative policies
> say what each step gets, serializers transform state into token-efficient
> text, and a middleware factory injects it at runtime.

## Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Context Engineering Flow                         │
│                                                                      │
│  ┌──────────────┐     ┌───────────────────┐     ┌────────────────┐  │
│  │   Policies   │────►│ Middleware Factory │────►│  Serializers   │  │
│  │ policies.py  │     │   middleware.py    │     │ serializers.py │  │
│  └──────────────┘     └───────────────────┘     └────────────────┘  │
│         │                      │                        │            │
│         │                      ▼                        │            │
│         │            ┌─────────────────┐               │            │
│         └───────────►│ inject_context  │◄──────────────┘            │
│                      │   (middleware)  │                             │
│                      └────────┬────────┘                             │
│                               ▼                                      │
│                      ┌─────────────────┐                             │
│                      │  context message │                            │
│                      │  appended to req │                            │
│                      └─────────────────┘                             │
└─────────────────────────────────────────────────────────────────────┘
```

Three components:

1. **Policies** — declarative definitions of what each step receives.
2. **Serializers** — token-efficient transforms from state → text.
3. **Middleware factory** — builds runtime context injection from a policy.

## 1. Policies

A policy is the single source of truth for what context a step gets.

```python
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ContextField:
    name: str                                          # state field name
    serialization: Literal["compact", "full", "json"]  # tier
    required: bool = True
    description: str = ""
    edit_field: bool = False   # the step's own artifact, for re-runs/edits


@dataclass(frozen=True)
class StepContextPolicy:
    step: str
    fields: tuple[ContextField, ...]
    description: str = ""


# Registry for runtime lookup
CONTEXT_POLICIES: dict[str, StepContextPolicy] = {
    "analyze": ANALYZE_POLICY,
    "summarize": SUMMARIZE_POLICY,
}


def get_policy(step: str) -> StepContextPolicy:
    return CONTEXT_POLICIES[step]
```

## 2. Serializers

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

## 3. Middleware Factory

The factory builds a context injector from a policy at runtime, so a policy
change automatically changes behavior — no per-step middleware to maintain.

```python
def create_context_injector(step: str):
    policy = get_policy(step)

    @wrap_model_call
    def inject_context(request, handler):
        parts = []
        for field in policy.fields:
            value = request.state.get(field.name)
            if value is None:
                continue
            serializer = get_serializer(field.name, field.serialization)
            label = FIELD_LABELS.get(field.name, field.name.title())
            if field.edit_field:
                label = f"{label} to Edit"
            parts.append(f"## {label}\n{serializer(value)}")

        context = "\n\n---\n\n".join(parts)
        messages = [*request.messages, HumanMessage(content=context)]
        return handler(request.override(messages=messages))

    return inject_context
```

Use it when building a chain:

```python
return create_agent(
    model=chat_model,
    system_prompt=ANALYZE_PROMPT,
    middleware=[create_context_injector("analyze")],
)
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
└── middleware.py     # create_context_injector factory, FIELD_LABELS
```
