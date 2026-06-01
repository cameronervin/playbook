# Agent Layer — Architecture & Extension Guide

This package is the LangGraph agent subsystem for the scaffold. It ships **one
generic workflow, `example`**, that exercises every folder so you can copy the
pattern for your real domain workflows.

> The `example` workflow is intentionally minimal: load entity context →
> run one structured LLM chain → persist the result. Everything else
> (token budgeting, prompt caching, tool registry, middleware, guardrails) is
> wired in so the *shape* is production-grade even though the logic is trivial.

---

## 1. Composition flow: chains → nodes → graphs → executors

```
prompts/  + tools/        →  chains/        (one LLM-call unit)
chains/   + persistence   →  nodes/         (load_state, chain node, save_state, router)
nodes/                    →  graphs/        (StateGraph topology, pure structure)
graphs/   + checkpointer  →  builders/      (compose + compile)
compiled graph            →  executors/     (graph.ainvoke driven from the API)
```

Read it bottom-up when wiring, top-down when debugging:

| Layer | File(s) | Responsibility |
|-------|---------|----------------|
| State | `states/example_state.py` | `TypedDict` with `messages` (`add_messages` reducer), `example_id`, `decision`, `loaded_context`, `result`. `ExampleResult` is the structured output schema. |
| Prompt | `prompts/example_prompt.py` | Base system prompt string. Tool snippets are appended at compose time, not here. |
| Tools | `tools/tool_registry.py` | Frozen `ToolSpec` rows in `TOOL_REGISTRY`. `tools/tool_assignment.py` resolves enabled tools and maps them to chains. `tools/tool_prompts.py` holds per-(chain, tool) prompt snippets. `tools/example_kb_tool.py` is the one generic tool. |
| Context | `context/policies.py` (what each chain receives), `context/serializers.py` (how state is rendered), `context/token_budget.py` (trim/guard), `context/prompt_cache.py` (cache routing), `context/middleware/example_middleware.py` (assembles all of the above into a `wrap_model_call` injector), `context/prompt_composers/example_prompt_composer.py` (base prompt + tool snippets). |
| Chain | `chains/example_chain.py` | `create_agent(...)` bound to prompt + `response_format=ExampleResult` + `state_schema=ExampleState` + the context-injection middleware. |
| Nodes | `nodes/example/{load_state,chains,router,save_state}.py` | `load_state` hydrates state from DB; `chains.py` wraps chain calls with timeout/error conversion; `router.py` dispatches on `state["decision"]`; `save_state` persists output. |
| Graph | `graphs/example_graph.py` | Pure topology: `START → load_state → (router) → example_node → save_state → END`. No construction logic. |
| Builders | `builders/{chains_builder,nodes_builder,graphs_builder}.py` | `chains_builder` builds chains (resolving tools + composing prompts); `nodes_builder` builds nodes from chains; `graphs_builder` composes both and compiles the graph. |
| Executor | `executors/example_executor.py` | `ExampleExecutor.execute()` builds the initial state + invoke config and calls `graph.ainvoke()`. |
| Cross-cutting | `guardrails.py` (message scoping + loop guard), `retry.py` (`RetryHandler` with backoff), `utils/` (pure helpers). |

---

## 2. How the builders wire it (called once at startup)

`builders/graphs_builder.py::compile_example_graph(...)` is the single public
entry point:

1. `compose_example_dependencies` →
   - `create_example_chain_set(chat_model)` (chains_builder): resolves active
     tools via `resolve_active_tools(settings)`, composes per-chain prompts via
     `build_example_prompts`, assigns tools via `build_workflow_chain_tool_map`,
     and constructs each chain.
   - `create_example_node_set(chains, get_session, storage)` (nodes_builder):
     turns chains into nodes (plus `load_state`/`save_state`).
2. `create_example_graph(nodes)` (graphs) builds the `StateGraph`.
3. `.compile(checkpointer=...)` returns the runnable graph.

---

## 3. How the executor is invoked from `main.py`

`main.py` wires the agent layer inside its lifespan:

```python
from app.agents.builders import compile_example_graph
from app.agents.executors import ExampleExecutor

example_graph = compile_example_graph(
    chat_model=chat_model,
    get_session=get_db,
    storage=storage,
    checkpointer=checkpointer,
)
example_executor = ExampleExecutor(example_graph, tracing_enabled=settings.TRACING_ENABLED)
app.state.example_executor = example_executor
```

A route then depends on `get_example_executor` and calls:

```python
result = await executor.execute(example_id=..., phase="example", messages=[...])
structured = result["result"]   # an ExampleResult
```

**Exported names main.py relies on:**
- `app.agents.builders.compile_example_graph`
- `app.agents.executors.ExampleExecutor`

---

## 4. Recipes

### Add a new chain (to the existing workflow)
1. Add a prompt constant in `prompts/`.
2. If it needs context, add a `PhaseContextPolicy` to `context/policies.py` and
   any serializers to `context/serializers.py`.
3. Create `chains/<name>_chain.py` (copy `example_chain.py`); use
   `create_context_injector("<name>")`.
4. Add the base prompt to `EXAMPLE_BASE_PROMPTS` in the prompt composer.
5. Construct it in `create_example_chain_set` (chains_builder).

### Add a new node
1. Add the node fn (or factory) under `nodes/example/`.
2. Return it from `create_example_nodes` (or the node set builder).
3. Register it and its edges in `graphs/example_graph.py`.

### Add a new tool
1. Write a factory returning a `BaseTool` (see `tools/example_kb_tool.py`).
2. Add a prompt snippet + `ToolPromptKey` to `tools/tool_prompts.py`.
3. Append one `ToolSpec` to `TOOL_REGISTRY` in `tools/tool_registry.py` with an
   `enabled_predicate` and `workflow_chain_targets`. No builder/graph changes
   needed — assignment and prompt composition pick it up automatically.

### Add a new workflow
1. Add a state in `states/`, prompt(s) in `prompts/`, chain(s) in `chains/`.
2. Add a workflow literal to `ToolWorkflow` and an entry to
   `WORKFLOW_CHAIN_NAMES` in `tools/tool_registry.py`.
3. Add `nodes/<workflow>/` (load_state, chains, router, save_state).
4. Add `graphs/<workflow>_graph.py`.
5. Add `create_<workflow>_chain_set` / `_node_set` and a
   `compile_<workflow>_graph` to the builders.
6. Add an executor in `executors/` and wire it in `main.py`.
