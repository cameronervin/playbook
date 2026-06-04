# LLM Infrastructure — Stubs & Extension Guide

This package abstracts LLM access behind a provider interface so the rest of
the app never imports a vendor SDK directly.

## Pattern

```
BaseLLMProvider (ABC)          ← providers/base.py
   ├── GatewayLLMProvider      ← providers/gateway.py  (LiteLLM, OpenAI-compatible)
   └── DirectLLMProvider       ← providers/direct.py   (local/break-glass, per-use-case)

LLMProviderMode (StrEnum)      ← factory.py
get_llm_provider() @lru_cache  ← factory.py  (singleton, mode-driven)
get_llm_provider_dependency()  ← factory.py  (FastAPI Depends)
clear_all_caches()             ← factory.py  (test/reset)
```

Selection is driven by `settings.LLM_PROVIDER_MODE` (`direct` | `gateway`).

## Model Defaults

| Setting          | Default               | Used in       |
|------------------|-----------------------|---------------|
| `CHAT_MODEL`     | `claude-sonnet-4-6`   | direct mode   |
| `ADVANCED_MODEL` | `claude-opus-4-8`     | direct mode   |
| `LLM_CHAT_MODEL` | `claude-sonnet-4-6`   | gateway alias |
| `LLM_RESEARCH_MODEL` | `claude-opus-4-8` | gateway alias |

Gateway mode is the production default; direct mode is intended for local
development, smoke tests, or an explicit break-glass path. `DirectLLMProvider`
uses `langchain_anthropic.ChatAnthropic` by default.
Alternatives, already coded in `direct.py::_create_chat_model`:
`openai` (`langchain_openai`), `google` (`langchain_google_genai`), and
`gateway` (OpenAI-compatible client pointed at the LiteLLM gateway).

## Stubs (NotImplementedError until wired)

`get_research_model()` is intentionally a stub on both providers. It returns
the high-capability ("advanced") tier model. Implement it when a consumer
needs it:

- **Direct:** in `_get_research_model_cached`, call
  `_create_chat_model(settings.RESEARCH_PROVIDER, settings.ADVANCED_MODEL, settings.LLM_TEMPERATURE)`.
- **Gateway:** in `_get_gateway_research_model`, instantiate `ChatOpenAI` with
  `model=settings.LLM_RESEARCH_MODEL` and the gateway base URL/key.

## Adding a new direct provider

1. Add an API-key setting to `app/core/config.py` (e.g. `MISTRAL_API_KEY`).
2. Add a branch to `direct.py::_create_chat_model` returning the LangChain
   chat model for that provider.
3. Add the integration package to `backend/pyproject.toml`.

## Adding domain-specific model accessors

Vision/multimodal, embeddings, and image-generation accessors were
intentionally left out of this scaffold. To add one:

1. Add an `@abstractmethod` to `BaseLLMProvider` (e.g. `get_vision_model()`).
2. Implement it on `DirectLLMProvider` and `GatewayLLMProvider`, with a cached
   factory and a `clear_caches()` entry.
