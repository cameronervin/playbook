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
                   to the model as a tool message → model continues
```

Keep tools small and single-purpose. Business logic that doesn't need the model
to decide *when* to run it belongs in a deterministic graph **node**, not a
tool — nodes give you better retry handling and clearer separation of concerns.

## Built-in Tools

| Tool | Description |
|------|-------------|
| `example_tool` | Illustrative tool — echoes/transforms its input. Replace with your real tools. |

## Adding a Tool

1. Define the tool in `backend/app/agents/tools/`:

```python
from langchain_core.tools import tool


@tool
def example_tool(query: str) -> str:
    """Look up information for the given query.

    The docstring is the description the model sees — make it precise:
    say what the tool does and when to use it.
    """
    # ... perform the lookup / action ...
    return f"Result for: {query}"
```

2. Bind it to the chain/agent that should use it, in
   `backend/app/agents/chains/`:

```python
from app.agents.tools.example_tool import example_tool

def create_example_chain(chat_model):
    return create_agent(
        model=chat_model,
        system_prompt=EXAMPLE_PROMPT,
        tools=[example_tool],
    )
```

3. Add a row to the **Built-in Tools** table above.

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
