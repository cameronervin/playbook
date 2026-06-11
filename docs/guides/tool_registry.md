# Tool Registry Flow

The agent tool registry answers one question: which tools should each chain
receive when a graph is built?

Current shape:

```text
workflow -> chain -> tools
```

For athlete chat, the final assignment looks like:

```python
{
    "athlete_chat": {
        "athlete_chat": [search_playbook_knowledgebase],
    }
}
```

## Build Flow

1. `tool_registry.py` declares available tools as `ToolSpec` rows.
2. `resolve_active_tools(...)` builds only enabled tools.
3. `build_workflow_chain_tool_map(...)` assigns active tools to target chains.
4. `chains_builder.py` gives each chain its assigned tools and matching prompt
   snippets.
5. `create_agent(...)` binds those tools to the LangChain agent.

## Empty Buckets

This code creates the empty `workflow -> chain -> []` structure:

```python
assignments = {
    workflow: {chain: [] for chain in chains}
    for workflow, chains in WORKFLOW_CHAIN_NAMES.items()
}
```

It is the compact form of:

```python
assignments = {}

for workflow, chains in WORKFLOW_CHAIN_NAMES.items():
    assignments[workflow] = {}
    for chain in chains:
        assignments[workflow][chain] = []
```

With:

```python
WORKFLOW_CHAIN_NAMES = {
    "athlete_chat": ("athlete_chat",),
}
```

the result starts as:

```python
{
    "athlete_chat": {
        "athlete_chat": [],
    }
}
```

## Filling Buckets

This code adds active tools to their declared targets:

```python
for spec in registry:
    tool = tool_by_name.get(spec.tool_name)
    if tool is None:
        continue
    for workflow, chains in spec.workflow_chain_targets.items():
        chain_map = assignments.setdefault(workflow, {})
        for chain_name in chains:
            chain_map.setdefault(chain_name, []).append(tool)
```

Read it as:

```python
for each registered tool spec:
    find the active tool instance with the same name
    skip it if the tool was not enabled
    for each workflow and chain targeted by the spec:
        create missing workflow or chain buckets if needed
        append the tool to that chain's list
```

`setdefault(key, default)` means: get `dict[key]`; if the key does not exist,
create it with `default` first.

So this:

```python
chain_map.setdefault(chain_name, []).append(tool)
```

means:

```python
if chain_name not in chain_map:
    chain_map[chain_name] = []

chain_map[chain_name].append(tool)
```

## Prompt Tie-In

Tool assignment and tool prompting are separate but use the same tool names.
After tools are assigned, `chains_builder.py` passes active tool names to the
prompt composer. The composer appends snippets from `tool_prompts.py` only for
tools that are active for that chain.

That keeps base prompts tool-agnostic while ensuring the model gets instructions
for every tool it can actually call.
