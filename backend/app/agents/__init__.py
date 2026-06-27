"""Agent layer for Playbook workflows.

This package houses the LangGraph agent subsystem. The active product workflow
is athlete chat, executed by a Celery worker after the API persists the user
turn and assistant placeholder:

    states/   -> typed graph state extending LangChain AgentState
    prompts/  -> system prompt strings
    chains/   -> structured create_agent units
    nodes/    -> graph nodes (load_state -> safety -> agent -> save_state)
    graphs/   -> StateGraph topology
    executors/-> drives graph.astream() from worker tasks
    builders/ -> compose chains -> nodes -> graph and compile it
    tools/    -> knowledge-base retrieval tools
    context/  -> token budgeting, prompt cache, policies, serializers,
                 middleware (context injection) and prompt composers
    guardrails/ -> execution guardrails, retry policy, and safety checks
"""
