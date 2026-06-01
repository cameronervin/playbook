"""Agent layer for the scaffold.

This package houses the LangGraph agent subsystem. It demonstrates a single
generic ``example`` workflow that exercises every architectural folder:

    states/   -> typed graph state (TypedDict + add_messages reducer)
    prompts/  -> system prompt strings
    chains/   -> small LLM-call units (one create_agent per chain)
    nodes/    -> graph nodes (load_state -> chain -> save_state) + router
    graphs/   -> StateGraph topology
    executors/-> drives graph.ainvoke() from the API layer
    builders/ -> compose chains -> nodes -> graph and compile it
    tools/    -> declarative ToolSpec registry + runtime assignment
    context/  -> token budgeting, prompt cache, policies, serializers,
                 middleware (context injection) and prompt composers
    guardrails.py / retry.py -> cross-cutting execution safety

See ``STUBS.md`` for the full composition flow and "how to add X" recipes.
"""
