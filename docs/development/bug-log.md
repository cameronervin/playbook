# Bug Log

> Track bugs found during development and their resolution. Add a row when a bug
> is discovered; update `Status` and `Fix` as it progresses.

## Severity Scale

| Severity | Meaning |
|----------|---------|
| Critical | Data loss, security issue, or production outage |
| High | Major feature broken, no workaround |
| Medium | Feature impaired, workaround exists |
| Low | Cosmetic or minor inconvenience |

## Status Values

`Open` · `In Progress` · `Fixed` · `Won't Fix` · `Closed`

## Bugs

| ID | Date | Severity | Description | Status | Fix |
|----|------|----------|-------------|--------|-----|
| B-001 | 2026-06-07 | Low | Login page border utilities did not compile to the intended warm hairline tokens, causing visual drift from the Claude design reference. | Fixed | Added missing Tailwind v4 border theme tokens and kept login visual regression tests focused on SSO-only behavior. |
