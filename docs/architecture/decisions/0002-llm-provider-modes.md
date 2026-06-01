# ADR 0002 — LLM Provider Modes (Direct vs Gateway)

## Status

Accepted

## Context

The application calls large language models from multiple places (services and
agent graphs). We need to:

- Avoid coupling application/agent code to any one vendor SDK.
- Support a simple, low-dependency default for local development and small
  deployments.
- Allow centralized multi-provider routing, fallbacks, and cost/rate controls
  when running at scale.

Two transport options exist:

1. **Direct** — call the provider SDK (Anthropic by default) directly.
2. **Gateway** — route all traffic through a [LiteLLM](https://github.com/BerriAI/litellm)
   proxy that exposes an OpenAI-compatible API and can fan out to many providers.

## Decision

We introduce a `BaseLLMProvider` abstraction with a `get_chat_model()` factory.
All application and agent code depends on this abstraction — never on a vendor
SDK directly.

Transport is selected at runtime by the `LLM_PROVIDER_MODE` setting:

- `direct` (**default**) — Anthropic-first. Calls the provider SDK directly.
  Fewest moving parts; ideal for local dev and single-provider deployments.
- `gateway` — routes through a LiteLLM proxy. Use when you need multi-provider
  routing, automatic fallbacks, or centralized usage/cost tracking and rate
  limiting.

Model identity (`LLM_CHAT_MODEL`, model lists, etc.) is also configuration, so a
model or provider swap is a config change with no code change.

## Consequences

**Positive**
- Vendor independence — swap providers or models via env vars.
- Local dev stays simple (`direct`, single API key).
- Scaling path is built in (`gateway`) without rewriting agents.
- The eval/judge layer reuses the same factory, so it always tracks production
  model identity.

**Negative**
- Two transport paths to test and keep behaviorally consistent.
- Gateway mode adds an extra service (LiteLLM) and a network hop.
- Provider-specific features (e.g. prompt caching headers) must be validated in
  each mode before relying on them.

**Follow-ups**
- Document required env vars for each mode in `deploy/envs/`.
- Add a smoke test that exercises both modes against a cheap model.
