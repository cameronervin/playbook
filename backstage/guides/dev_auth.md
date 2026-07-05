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

Use the Developer SSO provider on the login screen. It opens a role menu with
`Athlete`, `New athlete`, `Admin`, and `Super admin` options, then starts the
same login flow as Google/Microsoft.

The frontend calls the local `/api/v1/auth/dev/login?persona={persona}`
contract behind that menu. The dev provider returns an authorization URL
pointed at the normal `/api/v1/auth/dev/callback` route. The callback validates
OAuth state, seeds the deterministic local user, creates the normal Playbook JWT
cookie, and redirects to the matching frontend route:

| Persona | Redirect |
|---------|----------|
| `athlete` | `/chat` |
| `new_athlete` | `/profile` |
| `admin` | `/admin` |
| `super_admin` | `/admin` |

Valid fake SSO personas are `athlete`, `new_athlete`, `admin`, and
`super_admin`. If `persona` is omitted by an API caller, the backend uses
`athlete`.

The older `/api/v1/dev/session/{persona}` browser shortcut has been removed; use
the login-screen Developer SSO menu for local browser validation.
