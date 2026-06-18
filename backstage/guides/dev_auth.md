# Dev Auth

Dev auth lets you test protected UI locally without Google or Microsoft SSO.

Enable it only in `backend/.env`:

```env
DEV_AUTH_ENABLED=true
ENVIRONMENT=local
DEBUG=true
```

Restart the backend after changing `.env`.

Pytest does not read `backend/.env`; tests inject their own settings with dev
auth disabled. This keeps local no-SSO browser testing from changing pytest
collection or route behavior.

## Fake SSO Provider

When dev auth is available, `GET /api/v1/auth/providers` also returns:

```json
{
  "provider": "dev",
  "label": "Developer SSO",
  "enabled": true,
  "login_url": "/api/v1/auth/dev/login"
}
```

The frontend can start the same login flow as Google/Microsoft by calling:

```text
http://localhost:8000/api/v1/auth/dev/login
http://localhost:8000/api/v1/auth/dev/login?persona=athlete
http://localhost:8000/api/v1/auth/dev/login?persona=new_athlete
http://localhost:8000/api/v1/auth/dev/login?persona=admin
http://localhost:8000/api/v1/auth/dev/login?persona=super_admin
```

The dev provider returns an authorization URL pointed at the normal
`/api/v1/auth/dev/callback` route. The callback validates OAuth state, seeds the
deterministic local user, creates the normal Playbook JWT cookie, and redirects
to the matching frontend route:

| Persona | Redirect |
|---------|----------|
| `athlete` | `/chat` |
| `new_athlete` | `/profile` |
| `admin` | `/admin` |
| `super_admin` | `/admin` |

Valid fake SSO personas are `athlete`, `new_athlete`, `admin`, and
`super_admin`. If `persona` is omitted, the backend uses `athlete`.

The older `/api/v1/dev/session/{persona}` browser shortcut has been removed; use
Developer SSO for local browser validation.
