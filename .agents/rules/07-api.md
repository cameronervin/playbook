# API Rules

## URL Conventions
```
GET    /api/v1/resources          # List
POST   /api/v1/resources          # Create
GET    /api/v1/resources/{id}     # Get one
PUT    /api/v1/resources/{id}     # Update
DELETE /api/v1/resources/{id}     # Delete
```

## Response Codes
| Code | Use |
|------|-----|
| 200 | Success (GET, PUT) |
| 201 | Created (POST) |
| 204 | No Content (DELETE) |
| 400 | Validation error |
| 401 | Not authenticated |
| 403 | Not authorized |
| 404 | Not found |

## DO
- Use plural nouns (`/users` not `/user`)
- Version APIs (`/api/v1/`)
- Return Pydantic models
- Use `response_model=` in decorators

## DON'T
- Use verbs in URLs (`/getUser`)
- Return raw dicts
- Expose internal IDs unnecessarily
