# Agent Tools

> How agent tools work and how to add one. Tools let an agent take actions
> (lookups, retrieval, calculations) during a graph run. They are registered in
> a central registry and bound to chains at build time.

## How Tools Work

A tool is a typed, named callable with a description the model uses to decide
when to invoke it. Tools are defined with LangChain's `@tool` decorator (which
produces a `ToolSpec`-style structured definition: name, description, input
schema, handler) and bound to the chains/agents that should have access.

```
Chain build time:  register tool → bind to agent (create_agent(tools=[...]))
Run time:          model decides to call tool → handler runs → result returned
                   to the model as a tool message → model returns structured output
```

Keep tools small and single-purpose. Business logic that doesn't need the model
to decide *when* to run it belongs in a deterministic graph **node**, not a
tool — nodes give you better retry handling and clearer separation of concerns.

## Built-in Tools

| Tool | Description |
|------|-------------|
| `search_playbook_knowledgebase` | Athlete chat profile for searching official Playbook KB sources before NIL, compliance, recruiting, reporting, or process guidance. |

The reusable implementation lives in `backend/app/agents/tools/knowledgebase.py`
as a profile-based factory, and active product tools are declared in
`backend/app/agents/tools/tool_registry.py`:

```python
ToolSpec(
    tool_name="search_playbook_knowledgebase",
    factory=_create_athlete_kb_tool,
    workflow_chain_targets={"athlete_chat": ("athlete_chat",)},
    prompt_keys=(ToolPromptKey("athlete_chat", "search_playbook_knowledgebase"),),
)
```

Use profile-specific tool names and descriptions for each agent. Keep the
provider call, result normalization, source-key formatting, and citation
metadata mapping in the reusable factory. Athlete chat records cited source keys
in structured output; `save_state` persists citations only when those keys match
tool-returned sources. The athlete KB profile filters retrieval with
`metadata_filter={"visibility_policy": {"scope": "all_athletes"}}`, matching the
visibility policy metadata stored during ingestion. Organization scope is bound
from trusted graph/runtime context and passed to the KB provider separately from
model-visible tool arguments, so the model cannot choose or override tenant
scope. Local KB results are normalized into citation-ready metadata including
Playbook `document_id`, `kb_service_document_id`, stable `chunk_id`,
`chunk_index`, score, source title/date, visibility policy, and metadata tags.
All admin-uploaded shared KB documents are treated as official for MVP, and
retrieval does not use priority ranking. `message_citations` stores the Playbook document and
chunk IDs in columns and keeps the rest in `source_metadata`.

## Adding a Tool

1. Define or reuse a tool factory in `backend/app/agents/tools/`:

```python
from langchain_core.tools import tool


@tool
def lookup_department_guidance(query: str) -> str:
    """Look up information for the given query.

    The docstring is the description the model sees — make it precise:
    say what the tool does and when to use it.
    """
    # ... perform the lookup / action ...
    return f"Result for: {query}"
```

2. Declare it in `backend/app/agents/tools/tool_registry.py`:

```python
ToolSpec(
    tool_name="search_playbook_knowledgebase",
    factory=_create_athlete_kb_tool,
    enabled_predicate=_kb_tools_enabled,
    workflow_chain_targets={"athlete_chat": ("athlete_chat",)},
)
```

3. Add any model-facing tool instructions in `tool_prompts.py`, keyed by
   `(chain, tool_name)`.

4. Let the graph builder call `resolve_active_tools(...)` and
   `build_workflow_chain_tool_map(...)`; do not create tool profiles directly in
   graph builders.

5. Add a row to the **Built-in Tools** table above.

## Guidelines

- **Type everything** — typed signatures drive the input schema the model sees.
- **Clear descriptions** — the docstring is the model's only guidance on when to
  call the tool.
- **No side effects without need** — prefer pure lookups; gate destructive
  actions behind explicit confirmation.
- **Don't import vendor SDKs in tools** — get the chat model from the provider
  factory; tools should focus on the action, not LLM transport.
- **Deterministic work → node, not tool** — if the orchestration always needs
  the step, model it as a graph node.
