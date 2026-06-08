# LLM Infrastructure — Stubs & Extension Guide

This package abstracts LLM access behind a provider interface so the rest of
the app never imports a vendor SDK directly.

## Pattern

```
BaseLLMProvider (ABC)          ← providers/base.py
   ├── LiteLLMProvider         ← providers/gateway.py  (LiteLLM, OpenAI-compatible)
   └── DirectLLMProvider       ← providers/direct.py   (local/break-glass)

LLMProviderMode (StrEnum)      ← factory.py
get_llm_provider() @lru_cache  ← factory.py  (singleton, mode-driven)
get_llm_provider_dependency()  ← factory.py  (FastAPI Depends)
clear_all_caches()             ← factory.py  (test/reset)
```

Selection is driven by `settings.LLM_PROVIDER_MODE` (`direct` | `litellm`).

## Model Defaults

| Setting | Default | Used in |
|---------|---------|---------|
| `LLM_PROVIDER_MODE` | `direct` | mode selector |
| `LLM_CHAT_MODEL` | `claude-sonnet-4-6` | direct model ID or LiteLLM alias |
| `LLM_DIRECT_PROVIDER` | `anthropic` | direct mode |
| `LITELLM_BASE_URL` | `http://localhost:4000` | LiteLLM mode |
| `LITELLM_API_KEY` | empty | LiteLLM mode |

LiteLLM mode is the deployed-environment default; direct mode is intended for
local development, smoke tests, or an explicit break-glass path.

## Adding a new direct provider

1. Add an API-key setting to `app/core/config.py` (e.g. `MISTRAL_API_KEY`).
2. Add a branch to `direct.py::_create_chat_model` returning the LangChain
   chat model for that provider.
3. Add the integration package to `backend/pyproject.toml`.

## Adding domain-specific model accessors

Vision/multimodal, embeddings, and image-generation accessors were
intentionally left out of this scaffold. To add one:

1. Add an `@abstractmethod` to `BaseLLMProvider` (e.g. `get_vision_model()`).
2. Implement it on `DirectLLMProvider` and `LiteLLMProvider`, with a cached
   factory and a `clear_caches()` entry.
