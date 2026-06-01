# API Endpoints

> Template — `examples` is an illustrative resource. Replace it with your real
> resources, following the REST conventions below. Keep this doc in sync with
> the code (update it whenever you add or change an endpoint).

Base URL: `/api/v1`

## REST Conventions

| Rule | Detail |
|------|--------|
| Plural nouns | `/examples`, not `/example` or `/getExample` |
| No verbs in URLs | Use the HTTP method to convey the action |
| Versioned | All routes live under `/api/v1` |
| Typed responses | Every route declares a Pydantic `response_model` |
| Status codes | 200 GET/PUT · 201 POST · 204 DELETE · 400/401/403/404 errors |
| Auth | Bearer token via `fastapi-users`; protected routes require it |

## Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness/readiness check |

```bash
curl http://localhost:8000/api/v1/health
# {"status": "ok"}
```

## Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register user |
| POST | `/auth/jwt/login` | JWT login |
| POST | `/auth/jwt/logout` | JWT logout |
| GET | `/auth/users/me` | Current user |

Auth is provided by `fastapi-users`. Add SSO/OAuth routes (e.g. `/auth/oauth/*`)
here when you configure a provider.

## Examples
| Method | Endpoint | Description | Success |
|--------|----------|-------------|---------|
| GET | `/examples` | List the current user's examples | 200 |
| POST | `/examples` | Create an example | 201 |
| GET | `/examples/{id}` | Get one example | 200 |
| PUT | `/examples/{id}` | Update an example | 200 |
| DELETE | `/examples/{id}` | Delete an example | 204 |

### List Examples
```bash
curl http://localhost:8000/api/v1/examples \
  -H "Authorization: Bearer <token>"
```

**Response** (200 OK):
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "First example",
      "description": null,
      "status": "draft",
      "created_at": "2026-01-01T10:00:00Z",
      "updated_at": "2026-01-01T10:00:00Z"
    }
  ],
  "total": 1
}
```

### Create Example
```bash
curl -X POST http://localhost:8000/api/v1/examples \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "First example", "description": "Optional text"}'
```

**Response** (201 Created):
```json
{
  "id": "uuid",
  "name": "First example",
  "description": "Optional text",
  "status": "draft",
  "data": {},
  "created_at": "2026-01-01T10:00:00Z",
  "updated_at": "2026-01-01T10:00:00Z"
}
```

### Get Example
```bash
curl http://localhost:8000/api/v1/examples/{id} \
  -H "Authorization: Bearer <token>"
```

Returns 200 with the example, or 404 if not found / not owned by the caller.

### Update Example
```bash
curl -X PUT http://localhost:8000/api/v1/examples/{id} \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Renamed", "status": "active"}'
```

Returns 200 with the updated example.

### Delete Example
```bash
curl -X DELETE http://localhost:8000/api/v1/examples/{id} \
  -H "Authorization: Bearer <token>"
```

Returns 204 No Content.

## Error Shape

Errors return a consistent JSON body:

```json
{
  "detail": "Example not found"
}
```

| Code | Meaning |
|------|---------|
| 400 | Validation error (malformed body, failed Pydantic validation) |
| 401 | Not authenticated |
| 403 | Authenticated but not authorized for this resource |
| 404 | Resource not found or not owned by caller |
