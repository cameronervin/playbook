# Git Rules

## Commit Format
```
<type>: <short description>
```

## Types
| Type | Use |
|------|-----|
| feat | New feature |
| fix | Bug fix |
| refactor | Code change |
| docs | Documentation |
| test | Tests |
| chore | Build, deps |

## DO
- Imperative mood ("Add" not "Added")
- Keep commits atomic
- Pull before push
- Use feature branches
- Tag every release merge to `main` (annotated: `git tag -a vX.Y.Z -m "..."`)
- Sync hotfixes back to `develop` and active `release/*`

## DON'T
- Commit `.env` files
- Force push to `main` or `develop`
- Commit broken code
- Merge features directly to `main` (always go through `develop` → `release/*`)
- Delete `release/*` branches (they serve as historical records)

## Branch Names
| Pattern | Use |
|---------|-----|
| `feature/<description>` | New functionality (from `develop`) |
| `bugfix/<description>` | Non-critical bug fix (from `develop`) |
| `hotfix/<description>` | Critical production fix (from `main`) |
| `release/<N>` | Release stabilization (from `develop`) |

```
feature/SSO-login
feature/kb-account-scoping
bugfix/B-011-toast-overlap
hotfix/fix-auth-crash
release/1
release/2
```

## Branching Strategy
See `docs/development/branching-strategy.md` for full model, release cadence, and merge rules.
