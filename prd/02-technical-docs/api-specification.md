# API Specification

> Generic API contract spec. Defines resources, request/response shapes, and
> status codes. The `examples` resource is illustrative. See
> `docs/api/endpoints.md` for the live endpoint reference.

## Conventions

- Base path: `/api/v1`.
- Plural-noun resources; HTTP method conveys the action (no verbs in URLs).
- Every endpoint declares a Pydantic `response_model`.
- Bearer-token auth via `fastapi-users`; protected routes require it.
- Errors return `{ "detail": "..." }`.

## Status Codes

| Code | Use |
|------|-----|
| 200 | Success (GET, PUT) |
| 201 | Created (POST) |
| 204 | No Content (DELETE) |
| 400 | Validation error |
| 401 | Not authenticated |
| 403 | Authenticated but not authorized |
| 404 | Not found / not owned |

## Resources

### Health

| Method | Path | Auth | Response |
|--------|------|------|----------|
| GET | `/health` | none | `{ "status": "ok" }` |

### Examples

| Method | Path | Auth | Request | Success |
|--------|------|------|---------|---------|
| GET | `/examples` | yes | query: `page`, `page_size` | 200 `ExampleList` |
| POST | `/examples` | yes | `ExampleCreate` | 201 `Example` |
| GET | `/examples/{id}` | yes | — | 200 `Example` |
| PUT | `/examples/{id}` | yes | `ExampleUpdate` | 200 `Example` |
| DELETE | `/examples/{id}` | yes | — | 204 |

## Schemas

### ExampleCreate
```json
{
  "name": "string (required, 1..255)",
  "description": "string | null",
  "data": "object (default {})"
}
```

### ExampleUpdate
```json
{
  "name": "string | null",
  "description": "string | null",
  "status": "draft | active | archived | null",
  "data": "object | null"
}
```
All fields optional; omitted fields are unchanged.

### Example (response)
```json
{
  "id": "uuid",
  "owner_id": "uuid",
  "name": "string",
  "description": "string | null",
  "status": "draft",
  "data": {},
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

### ExampleList (response)
```json
{
  "items": [ /* Example[] */ ],
  "total": 0,
  "page": 1,
  "page_size": 20
}
```

## Authorization Rules

- All `examples` operations are scoped to the authenticated user.
- A user may only read/update/delete examples they own. Accessing another
  user's example returns 404 (existence is not leaked).

## Versioning

Breaking contract changes go under a new path prefix (`/api/v2`). Additive,
backward-compatible changes stay in `/api/v1`.
