# Branching Strategy

> Template — adjust cadence and protection rules to suit your team.

## Overview

This project uses a **hybrid Git Flow / GitHub Flow** model:

- A long-lived `main` (production) and `develop` (integration) branch.
- **Short-lived feature/bugfix branches** with PR-based review.
- **Release branches** cut from `develop` for stabilization.
- A **fast hotfix path** from `main` for critical production fixes.
- **Conventional Commits** for all commit messages.

## Branch Model

### Long-Lived Branches

| Branch | Purpose | Source | Protected |
|--------|---------|--------|-----------|
| `main` | Production-ready code. Every merge is tagged and deployable. | — | Yes — no direct pushes |
| `develop` | Integration branch. Feature/bugfix branches merge here via PR. | `main` (initial) | Yes — no direct pushes |

### Release Branches

| Branch | Purpose | Source | Lifecycle |
|--------|---------|--------|-----------|
| `release/N` | Stabilization for release N. Bug fixes and version bumps only — never new features. | `develop` | Cut when release enters stabilization; frozen after it ships |

### Short-Lived Branches

| Pattern | Purpose | Source | Target |
|---------|---------|--------|--------|
| `feature/<description>` | New functionality | `develop` | `develop` via PR |
| `bugfix/<description>` | Non-critical bug fix | `develop` | `develop` via PR |
| `hotfix/<description>` | Critical production fix | `main` | `main` via PR, then sync to `develop` + active `release/*` |

## Naming Conventions

```
feature/example-crud
feature/sso-login
bugfix/list-pagination
hotfix/fix-auth-crash
release/1
```

Rules: lowercase with hyphens; include a ticket/bug ID when applicable; keep
names concise but descriptive.

## Merge Direction

```
feature/*  ──PR──►  develop
bugfix/*   ──PR──►  develop
develop    ──cut──►  release/N  ──merge──►  main  (tagged)
release/N  ──merge──►  develop  (sync back)
hotfix/*   ──PR──►  main  (tagged)  ──merge──►  develop + release/N
```

## Conventional Commits

Format: `<type>: <short description>` (imperative mood, e.g. "add" not "added").

| Type | Use |
|------|-----|
| feat | New feature |
| fix | Bug fix |
| refactor | Code change that neither fixes a bug nor adds a feature |
| docs | Documentation only |
| test | Tests only |
| chore | Build, deps, tooling |

Examples:

```
feat: add example CRUD endpoints
fix: handle missing owner_id on example create
docs: document LLM provider modes
```

## Versioning

Semantic versioning: **`MAJOR.MINOR.PATCH`**.

- **MAJOR** — release scope / breaking changes.
- **MINOR** — backward-compatible features.
- **PATCH** — bug fixes and hotfixes.

Tag every merge to `main` with an annotated tag:

```bash
git tag -a v1.1.0 -m "Release 1.1.0 — example CRUD, auth hardening"
git push origin v1.1.0
```

## Branch Protection (recommended)

| Branch | Rules |
|--------|-------|
| `main` | Require PR, require CI pass, require 1 approval, no force push, no deletions |
| `develop` | Require PR, require CI pass, no force push |
| `release/*` | Require PR for merges, require CI pass |

## Decision Guide

```
New feature?               → feature/* from develop → PR to develop
Non-critical bug?          → bugfix/*  from develop → PR to develop
Critical production bug?   → hotfix/*  from main    → PR to main, tag, deploy,
                                                      then sync to develop + release/N
Preparing a release?       → cut release/N from develop → stabilize → merge to
                                                      main, tag, deploy → merge back to develop
```

## Related Documentation

- [Bug Log](bug-log.md)
- [Tech Debt Tracker](tech-debt-tracker.md)
