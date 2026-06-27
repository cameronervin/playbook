# ADR 0003 — Explicit Backend Settings Injection

## Status

Accepted

## Context

The backend previously instantiated `Settings()` at import time and many modules
imported a process-global `settings` object. That made local runtime `.env`
values, such as `DEV_AUTH_ENABLED=true`, affect pytest collection and route
tests before fixtures could install a test-safe configuration.

## Decision

Backend code now keeps `Settings` as the single configuration model, but loads
runtime settings through `get_settings()` only at process boundaries. FastAPI
apps are created with `create_app(app_settings=...)`, store the resolved object
on `app.state.settings`, and expose it through request dependencies. Services,
auth dependencies, infrastructure factories, Celery worker creation, scripts,
and eval helpers accept or resolve explicit settings instead of importing a
global singleton.

Pytest installs a deterministic `Settings(_env_file=None, ...)` object before
importing app modules, so developer `.env` values remain local-runtime-only.

## Consequences

**Positive**
- Tests are isolated from developer `.env` values.
- Runtime validation still happens when `get_settings()` is called.
- Multiple app instances can be built with different settings in the same test
  process.
- Config-dependent services and factories are easier to reason about.

**Negative**
- Constructors and factories that depend on config now require a `Settings`
  object or request-scoped settings dependency.
- Celery and uvicorn entrypoints remain the explicit places where runtime
  settings are loaded, so those boundaries need to stay visible.
