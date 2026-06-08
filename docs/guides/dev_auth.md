# Dev Auth

Dev auth lets you test protected UI locally without Google or Microsoft SSO.

Enable it only in `backend/.env`:

```env
DEV_AUTH_ENABLED=true
ENVIRONMENT=local
DEBUG=true
```

Restart the backend after changing `.env`.

Open one of these backend URLs in your browser:

```text
http://localhost:8000/api/v1/dev/session/athlete
http://localhost:8000/api/v1/dev/session/new_athlete
http://localhost:8000/api/v1/dev/session/admin
http://localhost:8000/api/v1/dev/session/super_admin
```

The backend seeds the local user, creates the normal Playbook JWT, stores it in
the HttpOnly `access_token` cookie, then redirects to the frontend:

| Persona | Redirect |
|---------|----------|
| `athlete` | `/chat` |
| `new_athlete` | `/profile` |
| `admin` | `/admin` |
| `super_admin` | `/admin` |

When disabled, the `/api/v1/dev/session/*` routes are not registered.
