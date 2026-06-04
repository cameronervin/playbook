# ADR 0002 — LLM Provider Modes (Direct vs Gateway)

## Status

Accepted

## Context

The application calls large language models from multiple places (services and
agent graphs). We need to:

- Avoid coupling application/agent code to any one vendor SDK.
- Centralize provider API keys outside application services.
- Allow centralized multi-provider routing, fallbacks, spend tracking, budgets,
  and rate controls when running at scale.
- Preserve a simple direct path for local development and emergency fallback.

Two transport options exist:

1. **Gateway** — route all traffic through a [LiteLLM](https://github.com/BerriAI/litellm)
   proxy that exposes an OpenAI-compatible API and can fan out to many providers.
2. **Direct** — call the provider SDK directly for local or break-glass use.

## Decision

We introduce a `BaseLLMProvider` abstraction with a `get_chat_model()` factory.
All application and agent code depends on this abstraction — never on a vendor
SDK directly.

Transport is selected at runtime by the `LLM_PROVIDER_MODE` setting:

- `gateway` (**default**) — routes through a LiteLLM proxy. Use for production
  traffic that needs centralized credentials, model aliases, multi-provider
  routing, automatic fallbacks, usage/cost tracking, budgets, and rate limiting.
- `direct` — calls the provider SDK directly. Use only for local development,
  smoke tests, or an explicit break-glass path.

Model identity (`LLM_CHAT_MODEL`, model lists, etc.) is also configuration, so a
model or provider swap is a config change with no code change.

## Consequences

**Positive**
- Vendor independence — swap providers or models via env vars.
- Provider credentials are centralized in the gateway instead of spread across app services.
- Local dev and emergency fallback remain possible through `direct`.
- The eval/judge layer reuses the same factory, so it always tracks production
  model identity.

**Negative**
- Two transport paths to test and keep behaviorally consistent.
- Gateway mode adds an extra service (LiteLLM) and a network hop.
- Provider-specific features (e.g. prompt caching headers) must be validated in
  each mode before relying on them.

**Follow-ups**
- Document required env vars for each mode in `deploy/envs/`.
- Add smoke tests that exercise gateway mode by default and direct mode as a fallback.
