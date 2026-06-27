# ADR 0003: Auth Provider Boundary

## Status

Accepted

## Context

Playbook signs users in with Google and Microsoft OAuth/OIDC, but the product's
identity policy is not provider-specific. The backend owns organization lookup,
role assignment, profile-completion routing, app JWT cookies, and token hygiene.
Provider SDK calls are external-integration concerns and should not make
`AuthService` responsible for Google/Microsoft protocol details.

Local development also needs a fake SSO mode that exercises the normal auth
flow without requiring Google or Microsoft credentials.

## Decision

Provider-specific OAuth mechanics live under `backend/app/infrastructure/auth/`.
The infrastructure package exposes a small provider-client protocol, normalized
`OAuthIdentity` DTO, HTTPX OAuth adapters for Google/Microsoft, and a local-only
dev provider. `AuthService` consumes those abstractions and remains responsible
for Playbook user/account upsert, session issuance, role/profile routing, and
sanitized auth logging.

The older `/api/v1/dev/session/{persona}` shortcut has been retired so local
browser validation uses the same login/callback path as real SSO. A `dev` auth
provider is exposed only when `DEV_AUTH_ENABLED=true`, `DEBUG=true`, and the
environment is local/development.

## Consequences

- Adding or replacing SSO providers should usually require a new infrastructure
  adapter, not changes to route logic or user repositories.
- Provider tokens remain internal to the backend and are never returned to the
  frontend.
- The local fake SSO provider can test state validation, callback handling, app
  session cookies, and frontend provider selection without external credentials.
- FastAPI routes stay thin and continue to delegate auth behavior to services.
