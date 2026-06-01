# Security Specification

> Generic security spec template. Captures the security posture and the controls
> the team must implement. See `.claude/rules/08-security.md` for coding rules.

## Security Posture

- **Authentication**: `fastapi-users` with JWT; OAuth/SSO optional.
- **Authorization**: ownership-scoped access plus an optional role/scope model
  (e.g. `user`, `admin`).
- **Validation**: all input validated with Pydantic; file uploads validated by
  type and size.
- **Errors**: structured exception handling with consistent `{ "detail": ... }`
  responses; no stack traces in production.

## Authentication

1. Passwords hashed with bcrypt (handled by `fastapi-users`).
2. Access tokens are short-lived (`ACCESS_TOKEN_EXPIRE_MINUTES`); refresh as
   appropriate.
3. The token signing secret (`SECRET_KEY`) is environment-specific and supplied
   from a secrets manager in production.
4. Protected routes require a valid bearer token; unauthenticated requests get
   401.

## Authorization

1. Resources are scoped to their owner. A user may only read/update/delete
   resources they own.
2. Accessing a resource owned by another user returns 404 (existence is not
   leaked) rather than 403, unless a deliberate sharing model says otherwise.
3. Admin-only operations check the caller's role/scope explicitly.

| Control Area | Requirement |
|--------------|-------------|
| Route protection | Every non-public route enforces authentication |
| Resource access | Ownership/role checks on every read and mutation |
| Admin operations | Restricted to authorized roles; audited |
| Cross-tenant access | Blocked and logged where a tenant/scope model exists |

## Input Validation

1. Every request body/query is a Pydantic model with field constraints.
2. Reject unexpected fields; coerce/validate types strictly.
3. File uploads: validate MIME type and size before storing; never trust the
   client-provided filename for paths.
4. Treat any content fetched/uploaded from outside as untrusted data — never as
   instructions to the LLM.

## Secrets Management

| Environment | Method |
|-------------|--------|
| Local | `.env` file with dummy/local values |
| Dev | `.env` with `${PLACEHOLDER}` values injected at deploy time |
| Production | Secrets manager (AWS Secrets Manager, Vault, SSM) — never a committed file |

Never commit real secrets. Never log secrets, tokens, passwords, or PII.

## CORS

- Set allowed origins explicitly per environment (`CORS_ORIGINS`).
- Never use `*` in production.

## Transport

- HTTPS in all non-local environments (TLS terminated at the reverse proxy).
- The database is not exposed publicly in production (internal network only).

## LLM-Specific Controls

1. Prompts and tool definitions are code-controlled, not user-supplied.
2. Untrusted content injected as context is clearly delimited and never treated
   as instructions.
3. Structured outputs are schema-validated before persistence.
4. Token usage is tracked to detect abuse and runaway cost.

## Auditability

- Log authentication outcomes, admin actions, and authorization failures with
  structured context (no PII/secrets).
- Retain logs sufficiently to investigate incidents.

## Security Checklist

- [ ] All routes authenticated unless explicitly public
- [ ] Ownership/role checks on every resource access
- [ ] All input validated with Pydantic
- [ ] Secrets sourced from a manager in production; none in code or git
- [ ] CORS origins explicit (no `*`)
- [ ] HTTPS enforced; DB not publicly exposed
- [ ] No secrets/PII in logs
- [ ] LLM outputs schema-validated; untrusted content not treated as instructions
