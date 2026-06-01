"""Context engineering: policies, serializers, budgeting, and middleware.

This package decides *what* context each chain receives and *how* it is
serialized and budgeted before being injected into the LLM call. The flow:

    policies.py        -> declares which state fields a chain receives + tier
    serializers.py     -> turns a state value into a token-efficient string
    token_budget.py    -> trims/guards injected context against a per-chain budget
    prompt_cache.py    -> stable cache-routing metadata for prompt caching
    middleware/        -> assembles the above into a wrap_model_call injector
"""
