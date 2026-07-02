# Frontend Wireframe Implementation Plan

## Summary
This plan makes the Claude Design wireframes durable for phased implementation across multiple coding-agent cycles. The goal is to port the Login, Home/chat, and Admin designs from `backstage/design/` into the frontend with high visual fidelity while respecting the current Playbook architecture, PRD, and implemented backend API surface.

Target frontend stack:

- Next.js App Router with TypeScript for routing, layouts, and server/client component boundaries.
- Tailwind CSS v4 for token-backed styling through `@theme` and shared global utilities.
- TanStack Query for backend/server state, request caching, mutations, invalidation, and loading/error states.
- Zustand for ephemeral client UI state such as panels, active selections, composer preferences, settings modal state, and temporary fixture-backed UI controls.

Component primitive strategy:

- Use Radix UI primitives directly for accessible overlays, menus, tabs, tooltips, and switches.
- Do not initialize shadcn/ui for the wireframe port unless the team explicitly decides to adopt its generator/registry workflow later.
- Treat shadcn/ui as an optional reference pattern only: it is built on Radix and Tailwind, but the production components should be local Playbook primitives styled from the `backstage/design/` handoff.

Target route model:

- `/login` for SSO entry.
- `/profile` for first-time athlete profile completion.
- `/chat` for the athlete-first chat workspace; admins may enter it explicitly from the account-menu switcher.
- `/admin` for default admin-only operations.
- `/` as an auth-aware redirect to the appropriate route.

Current route organization keeps `/login` and `/profile` under `src/app/(auth)/`
for the shared auth stage, and `/chat` and `/admin` under
`src/app/(workspace)/` for the shared left/main/right workspace geometry. Route
groups must not change the public URL paths above.

Implementation should wire currently implemented backend APIs immediately and isolate planned-but-missing APIs behind typed fixture adapters so each phase can land cleanly.

## Loader Policy
- Route segments that can suspend must define `loading.tsx` fallbacks that preserve the target screen geometry: chat rail/thread/composer or admin rail/header/cards. Generic app-entry loading (`/` auth redirect and `/login` pre-page route fallback) uses the minimal centered Playbook mark with `Loading ...` on a plain warm-charcoal background. Mounted page data loading keeps its shaped skeletons, including the login auth-card provider skeleton. Do not use plain `Loading [page]...` copy as a page fallback.
- Treat TanStack Query first-load states and background refetch states differently. Use shaped skeletons only when no useful cached data exists; keep existing content visible during `isFetching` and add a quiet token-backed refresh indicator.
- Loader visuals must use Playbook tokens and motion classes from `globals.css` (`pb-skeleton`, `pb-spin`, `pb-think`, `pb-streaming`) and honor `prefers-reduced-motion`.
- Skeletons should be structural-only: render stable chrome, headings, fixed controls, and persistent layout chrome directly; skeletonize only unknown data-backed regions; omit nonessential helper copy, subtitles, footer shimmer bars, and fake input-content placeholders. Stable copy that materially defines a control's footprint, such as the chat composer AI disclaimer, should remain visible.
- Interaction loaders should appear in the workflow surface itself: chat submit shows the user bubble plus PlaybookAI thinking row, admin insight generation skeletonizes the AI summary, and KB document processing uses info-tone spinner status.

## Phase 1: Design System Foundation
- Move the Playbook design assets from `backstage/design/source/` into the frontend asset structure: fonts, favicon, logo mark reference, and approved provider-logo references.
- Load Archivo, Sora, and Inter with `next/font/local` in `frontend/src/app/layout.tsx`; expose CSS variables for `--font-display`, `--font-display-alt`, and `--font-body`.
- Replace scaffold tokens in `frontend/src/app/globals.css` with the Playbook OSU orange and warm charcoal system from `backstage/design/source/colors_and_type.css`, expressed through Tailwind v4 `@theme` where utilities are needed.
- Add global utility styles for semantic type classes, reduced-motion-safe animations, scrollbars, ambient background layers, focus-visible rings, and dark app shell defaults.
- Build shared primitives under `frontend/src/components/ui/`: Playbook mark, button, icon button, badge, card/surface, segmented control, switch, dialog, dropdown menu, tooltip, tabs, agent avatar, Microsoft logo, and Google logo.
- Use Radix primitives for dialogs, dropdown menus, tabs, tooltips, and switches. Keep styling token-backed and local to reusable primitives or feature components.
- Keep the component layer Playbook-owned instead of shadcn-generated: create local wrappers around Radix primitives where needed, with Playbook names, tokens, and interaction states.
- Update the style folders in `.cursor/style/`, `.agents/style/`, and `.claude/style/` during Phase 1 so all agent surfaces use the same Playbook design tokens, UI patterns, typography, motion, icon exceptions, and Radix primitive strategy.
- Update every reference to those style guides across `.cursor`, `.agents`, and `.claude` so agents are pointed at the correct folder-local style files instead of stale `.claude`-only paths.
- Update frontend rules 13 and 14 in all three agent folders:
  - `.cursor/rules/13-frontend-design-standards.mdc`
  - `.cursor/rules/14-frontend-code-organization.mdc`
  - `.agents/rules/13-frontend-design-standards.md`
  - `.agents/rules/14-frontend-code-organization.md`
  - `.claude/rules/13-frontend-design-standards.md`
  - `.claude/rules/14-frontend-code-organization.md`
- Preserve the design handoff's explicit exceptions: the Playbook mark and SSO provider logos may be inline SVG components; other icons should use `lucide-react` unless a custom SVG asset is genuinely needed.
- Remove scaffold visual assumptions from the frontend, including the generic blue/gray token system and example app styling.

## Phase 2: Routing, Auth, and API Interfaces
- Add frontend routes for `/login`, `/profile`, `/chat`, and `/admin`; replace the scaffold home page with a redirecting root route.
- Organize the routes with non-URL-changing App Router groups: `(auth)` for login/profile and `(workspace)` for chat/admin.
- Update `frontend/src/app/layout.tsx` metadata from scaffold copy to Playbook-specific title, description, favicon, font variables, and body class.
- Update `frontend/src/lib/api/client.ts` to:
  - Send `credentials: "include"` for cookie-backed backend sessions.
  - Preserve browser-managed multipart headers for `FormData`.
  - Parse the backend structured error contract.
  - Support `204 No Content`.
- Add typed API modules and hooks for:
  - Auth providers, OAuth login URL, logout, and current session.
  - Current user and profile completion.
  - Conversation list, create, and detail.
  - Admin KB documents: list, upload, metadata update, retry, and delete.
  - Admin users: list and role update.
  - Audit logs where surfaced in admin views.
- Implement all backend/server-state reads and mutations through TanStack Query hooks; do not fetch server data directly inside component bodies or store server data in Zustand.
- Use Zustand only for client UI state that is not owned by the backend, including open panels, active tabs, selected citations, draft UI preferences, and temporary fixture-mode toggles.
- Add typed fixture adapters for APIs that remain planned in `backstage/api/endpoints.md`: chat message submit/stream, conversation file upload, analytics summary/query review, dashboard insights, and admin chat.
- Include the small backend auth compatibility change needed for real browser SSO: OAuth callbacks should redirect to `FRONTEND_URL + next_route` after setting the session cookie, while preserving JSON `SessionResponse` behavior for API-style tests or callers.
- Add route guard behavior:
  - Unauthenticated users go to `/login`.
  - Authenticated athletes with incomplete profiles go to `/profile`.
  - Athletes use `/chat`.
  - Admin and super-admin users default to `/admin` after auth-aware redirects and OAuth callbacks.
  - Admin and super-admin users can explicitly switch between `/admin` and `/chat` through real account-menu route links.
  - Athletes attempting `/admin` see the Admin design's access-denied state.

## Phase 3: Login Screen
- Recreate the Login wireframe at `/login` using the chosen defaults from `backstage/design/README.md`: tile SSO buttons, Microsoft first, no email/password, no support link, no system line, horizon background with motion enabled.
- Implement the full-viewport dark stage, ambient horizon field, centered rectangular card, Playbook lockup, "Log in to continue" heading, SSO buttons, and legal footer links.
- Fetch enabled providers from `GET /api/v1/auth/providers`; render unavailable providers disabled with clear but quiet UI states.
- On provider click, call the provider login endpoint, then navigate the browser to the returned `authorization_url`.
- Add error, loading, hover, active, focus-visible, and reduced-motion states.
- Keep provider logos as the only sanctioned multicolor elements.
- Add tests for provider ordering, disabled provider handling, login click redirect behavior, accessible button names, and no email/password fields.

## Phase 4: Athlete Chat Workspace
- Recreate the Home/chat wireframe at `/chat` as an athlete-first workspace that admin-capable users can enter by explicit choice.
- Build chat feature components under `frontend/src/components/features/chat/` for:
  - Nav rail with brand lockup, new chat action, searchable conversation history, account block, and settings/profile menu.
  - Center chat area with top bar, thread, empty state, thinking/streaming states, citation chips, and composer.
  - Sources panel with highlighted citation behavior.
  - Knowledge browser visuals only where role policy allows; admin-only creation/deletion controls must be hidden or disabled for athletes.
- Wire conversation list, create, and detail to the implemented backend APIs.
- Use typed fixture adapters for message submit, response streaming, citations, and conversation-scoped file upload until Phase 2 backend endpoints are implemented.
- Preserve key design defaults: horizon background, comfortable density, "Ask PlaybookAI" empty state, grounded citations at the bottom of answers, and sources hidden on an empty new chat but opened after citation click or explicit toggle on grounded conversations.
- Reuse existing app typography utilities such as `pb-ui-sm`, `pb-ui-xs`, and token-backed Tailwind type-scale classes for chat controls, history, menus, composer text, metadata, and source labels; do not carry over prototype-only arbitrary text sizes like `text-[13.5px]`.
- Implement composer behavior with Enter-to-send, Shift+Enter newline, disabled/loading states, and recoverable error display.
- Add settings modal support for the MVP Profile section only. Omit prototype-only Appearance/Tweaks controls unless a real settings store is introduced.
- Add tests for empty state, conversation selection, new chat, composer submit, streaming placeholder, citation click opening sources, source-panel toggle, settings modal, and role-gated KB controls.

## Phase 5: Admin Console
- Recreate the Admin wireframe at `/admin` with an admin-only shell and the access-denied state for athletes.
- Build admin feature components under `frontend/src/components/features/admin/` for:
  - Admin navigation and account/settings menu.
  - Insights dashboard with the AI summary as the hero hierarchy, embedded insight KPIs, topic/risk modules, query-volume chart, time-window selector, and generate action.
  - Knowledge-base management with collections, document rows, status pills, upload, retry, delete, official toggle, and metadata edit drawer.
  - Users & roles for super admins.
  - Admin analytics chat side panel.
- Wire KB document management to implemented admin KB APIs.
- Wire Users & roles to implemented super-admin user APIs.
- Keep Insights, dashboard insight generation, analytics query review, and admin chat on typed fixture adapters until Phase 4 backend APIs exist.
- Keep the admin analytics chat side panel on the shared `WorkspaceShell` side-panel geometry so it stays consistent with the chat sources panel.
- Enforce role behavior:
  - `admin` can access Insights and Knowledge base management where backend permits.
  - `super_admin` additionally sees Users & roles and can update roles.
  - If a viewer loses super-admin status while on Users & roles, route them back to Insights.
  - `athlete` sees Admins-only access denied.
- Add tests for admin route access, athlete denial, super-admin-only users route, KB status controls, retry/delete/update calls, role update calls, and fixture-backed dashboard states.

## Phase 6: Documentation and Agent Guidance
- Update `backstage/design/README.md` to link to this plan near the top.
- Update `frontend/FRONTEND.md` with the new route model, feature folders, Radix usage, auth/session assumptions, fixture-adapter policy, and verification commands.
- Confirm `.cursor/style/`, `.agents/style/`, and `.claude/style/` all contain matching Playbook-specific design tokens and UI patterns after the Phase 1 style-guide update.
- Confirm frontend rules 13 and 14 are synchronized across `.cursor/rules/`, `.agents/rules/`, and `.claude/rules/`, including Playbook's inline SVG exceptions, Tailwind v4 token policy, Radix primitive usage, TanStack Query/Zustand state boundaries, and actual frontend folder structure.
- Update `.claude/skills/frontend-design/SKILL.md` so Playbook UI work follows the provided handoff rather than inventing a new aesthetic direction.
- Update `AGENTS.md` and `CLAUDE.md` to name `backstage/design/` and this plan as required context for frontend wireframe work.
- Update `backstage/guides/setup.md` if new frontend dependencies, env vars, or auth redirect behavior affect local setup.
- Update `backstage/api/endpoints.md` only when backend API behavior changes, including the OAuth callback redirect compatibility if implemented.
- Update PRD implementation status files when each frontend phase becomes implemented and verified.

## Phase 7: Verification
- Run frontend checks after each implementation phase:
  - `cd frontend && npm run typecheck`
  - `cd frontend && npm run lint`
  - `cd frontend && npm test`
  - `cd frontend && npm run build`
- Run targeted backend auth tests after the OAuth callback redirect adjustment, then the existing backend test command if the change touches shared auth behavior.
- Use browser verification for visual phases:
  - Compare `/login`, `/chat`, and `/admin` against `backstage/design/design-reference/Login.html`, `Home.html`, and `Admin.html`.
  - Check desktop and mobile widths.
  - Check reduced-motion behavior.
  - Check keyboard navigation, focus rings, dialog escape handling, and menu/tab behavior.
- Confirm no Tweaks panel, mock navigation via `window.location`, CDN React, Babel standalone, or prototype global component patterns remain in production frontend code.
- Confirm no secrets, OAuth tokens, raw provider responses, or PII are logged or rendered unexpectedly.

## Public Interfaces
- Frontend routes:
  - `/login`
  - `/profile`
  - `/chat`
  - `/admin`
  - `/` redirect route
- New frontend dependencies:
  - Next.js App Router, already present in the frontend package.
  - Tailwind CSS v4, already present in the frontend package.
  - TanStack Query, already present in the frontend package.
  - Zustand, already present in the frontend package.
  - Radix UI primitives for accessible unstyled component behavior.
  - `@radix-ui/react-dialog`
  - `@radix-ui/react-dropdown-menu`
  - `@radix-ui/react-tabs`
  - `@radix-ui/react-tooltip`
  - `@radix-ui/react-switch`
  - `@testing-library/user-event`
- Shared frontend types:
  - `UserRole`
  - `CurrentUser`
  - `AuthProvider`
  - `ConversationSummary`
  - `ConversationDetail`
  - `ChatMessage`
  - `Citation`
  - `KBDocument`
  - `AdminUser`
  - `AuditLog`
  - Fixture-compatible analytics, dashboard insight, and admin-chat types.
- Backend compatibility behavior:
  - OAuth callback browser requests redirect to the frontend route returned by auth/profile state.
  - API-style callers can still receive the existing JSON session payload for tests and non-browser validation.

## Test Plan
- Unit and component tests:
  - Login provider rendering, disabled states, and redirect trigger.
  - Profile completion form validation and submit.
  - Route guard and access-denied behavior.
  - Chat empty state, conversation history, composer interactions, streaming placeholder, citations, and sources panel.
  - Admin navigation, KB document actions, users role changes, dashboard fixture states, and admin chat fixture behavior.
- API adapter tests:
  - Cookie credentials.
  - Structured error parsing.
  - JSON request handling.
  - Multipart `FormData` upload handling.
  - `204 No Content`.
- Backend tests:
  - OAuth callback redirect behavior.
  - Existing JSON response compatibility.
  - Cookie set/delete behavior remains intact.
- Visual verification:
  - Desktop and mobile screenshots.
  - Reduced-motion checks.
  - Focus and keyboard navigation checks.

## Assumptions and Defaults
- The design handoff in `backstage/design/README.md` is the visual source of truth.
- The static HTML files in `backstage/design/design-reference/` are visual references, not production code to copy verbatim.
- The source JSX in `backstage/design/source/` is structural reference material; production code must use TypeScript, imports/exports, route files, hooks, and feature modules.
- Prototype Tweaks controls are not part of the product.
- Radix UI is the primary primitive layer for accessible component behavior; shadcn/ui should not be initialized unless a later plan explicitly adopts its code-generation workflow.
- `/chat` is athlete-first per the PRD, but admin-capable users can explicitly enter it from `/admin`; root and OAuth defaults still send admins to `/admin`.
- Admin-only controls must be gated by real role data, not prototype role toggles.
- Implemented backend APIs should be wired directly.
- Planned backend APIs should be represented by typed fixture adapters that can be swapped later without rewriting UI components.
- Server state belongs in TanStack Query; client-only UI state belongs in Zustand.
- Styling should use Tailwind v4 token utilities and project globals, with raw values limited to documented design-source exceptions.
- No Auth.js/NextAuth dependency is added; the frontend uses the existing FastAPI OAuth/session system.
- TDD applies to non-trivial behavior; documentation-only edits do not require tests.
