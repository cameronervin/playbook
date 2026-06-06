# Phase 1 Next Steps

## Current Status

Phase 1 backend service scaffolding is implemented for OAuth/OIDC login,
profile completion, role management, audit logging, KB document control-plane
operations, signed KB webhooks, and the minimal athlete conversation shell.

The current API routes are registered under `/api/v1`, with service dependency
wiring centralized in `backend/app/api/v1/dependencies.py`.

## Service Build Status

| Service | Phase 1 implemented | Still left |
|---------|---------------------|------------|
| `AuthService` | OAuth provider listing, login URL creation, fake Google/Microsoft callback route coverage, callback user/account upsert, provider-token storage assertions, configured app JWT/cookie creation, authenticated logout, provider-token log redaction coverage, and next-route selection | Future provider-specific edge cases after real Google/Microsoft sandbox testing |
| `UserProfileService` | Current-user response, route coverage, and athlete profile completion/update with `profile_complete` and `next_route="/chat"` | Any future richer profile/admin-edit fields |
| `UserAdminService` | Super-admin user listing route coverage, org-scoped role update, `is_superuser` compatibility sync, and atomic audit logging | Future invite/activation/deactivation flows |
| `AuditLogService` | Single audit write path and super-admin org-scoped audit log query | Future dashboard/reporting behavior |
| `KBDocumentService` | Admin list/get/upload/metadata update/retry/delete route coverage, multipart `metadata_tags`, storage keying, lifecycle events, KB-service ingest/delete adapter calls, and audit logging | Real kb-service + MinIO/S3-compatible E2E test and stronger failure cleanup around partial upload/ingest failures |
| `KBDocumentWebhookService` | HMAC route coverage, signature verification, stale webhook rejection, status mapping, document status update, and event append | E2E validation against real kb-service payloads and broader status-mapping tests |
| `ConversationService` | Minimal athlete-owned shell route coverage: list/create/get conversations, bounded message loading, citation mapping, and athlete/org scoping | Phase 2 chat behavior: user message submission, assistant generation, streaming, LangGraph orchestration, KB retrieval, safety/refusal handling, file upload/extraction, `last_message_at` updates, and generated assistant message/citation persistence |

`ConversationService` is complete for the Phase 1 shell, but it is not the full
product chat experience. Phase 2 builds the actual AI conversation loop on top
of these persisted conversation records.

## Verified So Far

These checks passed after the Phase 1 service implementation:

```bash
cd backend && uv run pytest -q
cd backend && uv run ruff check app tests
cd backend && uv run python -c "from app.main import app; print(len(app.routes))"
```

These checks passed after the Phase 1 route-level test implementation:

```bash
cd backend
TEST_DATABASE_URL=postgresql+asyncpg://app:localpass@localhost:5433/playbook_test \
  ./.venv/bin/pytest -q
./.venv/bin/ruff check app tests
```

The focused OAuth callback hardening check passed with local Postgres on port
`5433`:

```bash
cd backend
TEST_DATABASE_URL=postgresql+asyncpg://app:localpass@localhost:5433/playbook_test \
  ./.venv/bin/pytest tests/integration/test_auth_routes.py -q -rs
```

The Alembic upgrade SQL rendered successfully offline:

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://app:localpass@localhost:5433/playbook \
  uv run alembic upgrade head --sql
```

## Ordered Remaining Work

1. Run the live DB migration check with local Postgres running on port `5433`:

   ```bash
   cd backend
   DATABASE_URL=postgresql+asyncpg://app:localpass@localhost:5433/playbook \
     uv run alembic upgrade head
   DATABASE_URL=postgresql+asyncpg://app:localpass@localhost:5433/playbook \
     uv run alembic downgrade -1
   ```

2. Update environment examples:
   - Add Google and Microsoft OAuth settings.
   - Add `API_PUBLIC_URL`, `OAUTH_STATE_SECRET`, default organization settings,
     and `KB_WEBHOOK_SECRET`.
   - Ensure deploy/local example values use the async Postgres driver:
     `postgresql+asyncpg://...`.

3. Verify KB service integration end to end:
   - Start backend, MinIO/S3-compatible storage, and kb-service locally.
   - Upload a sample PDF/DOCX/PPTX/XLSX through `/api/v1/admin/kb/documents`.
   - Confirm backend calls current kb-service ingest/delete/status route shapes.
   - Confirm signed webhook updates `kb_documents.processing_status` and appends
     `kb_document_events`.

4. Run the Phase 1 hardening pass:
   - Confirm 401/403 errors use the standard nested error response.
   - Confirm role guards match `athlete`, `admin`, and `super_admin` behavior.
   - Confirm all privileged role and KB actions write audit logs.
   - Confirm request IDs and actor context are present in structured logs.

## Known Blocker

The live Alembic upgrade/downgrade check requires local Postgres to be running
on `localhost:5433`. The backend should use an async SQLAlchemy URL such as:

```env
DATABASE_URL=postgresql+asyncpg://app:localpass@localhost:5433/playbook
```

Using a sync `postgresql://...` URL causes Alembic to look for `psycopg2`, which
is not installed in the backend environment.
