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
| B-002 | 2026-06-08 | Low | First-time athlete profile completion drifted from the login/auth design shell, using a generic page stage and card instead of the shared horizon background and raised auth card. | Fixed | Added shared auth stage/card components, moved `/login` and `/profile` onto them, and covered the profile shell plus SSO tile alignment with frontend tests. |
| B-003 | 2026-06-08 | Low | First-time athlete profile completion still used a wider, left-aligned, oversized modal hierarchy that did not match the compact login auth modal. | Fixed | Removed the profile-only wide card variant and normalized the profile lockup, heading, copy, fields, and CTA to the compact auth-card rhythm. |
| B-004 | 2026-06-08 | Low | Login and profile could drift again because each feature screen owned the auth background stage instead of sharing it at the route-layout boundary. | Fixed | Grouped `/login` and `/profile` under `src/app/(auth)/` and moved the shared `AuthStage` into the route-group layout. |
| B-005 | 2026-06-08 | Medium | Admin Insights rendered a rushed placeholder dashboard instead of the Claude design: standalone KPI cards, no AI-summary hierarchy, missing topic/risk/chart modules, and no right-side analytics chat panel. | Fixed | Added a shared workspace shell, grouped `/chat` and `/admin` under `src/app/(workspace)/`, rebuilt Admin Insights from typed fixtures, and added tests for the target dashboard and analytics chat panel. |
| B-006 | 2026-06-08 | Low | Admin workspace typography and header controls rendered larger than the Claude wireframe because compact product type roles were not exposed globally and small buttons used Tailwind default sizing. | Fixed | Added shared compact typography utilities, made `Button size="sm"` the canonical 36px app control, and updated admin pages to consume the shared hierarchy. |
| B-007 | 2026-06-08 | Low | Admin Insights header controls still looked mismatched because the time-window filter and adjacent action buttons used different class paths and no shared width. | Fixed | Reused the compact `pb-ui-sm` control typography in `Button size="sm"` and applied a shared 156px header-control width to the filter, regenerate, and explore actions. |
