# Frontend

Playbook’s frontend is a Next.js App Router app: **Next.js 15 + React 19 + Tailwind CSS v4 + TanStack Query + Zustand + Radix primitives**, with strict TypeScript.

## Getting Started

```bash
npm install
cp .env.local.example .env.local
npm run dev
```

Set `NEXT_PUBLIC_API_URL` to the FastAPI backend, usually `http://localhost:8000`.

| Script | Purpose |
|--------|---------|
| `npm run dev` | Start the dev server |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run lint` | ESLint |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run test` | Vitest unit/component tests |

## Routes

| Route | Purpose |
|-------|---------|
| `/` | Auth-aware redirect |
| `/login` | SSO-only login, Microsoft first then Google |
| `/profile` | First-time athlete profile completion |
| `/chat` | Athlete chat shell with conversation history and sources panel |
| `/admin` | Admin shell with insights, KB management, and super-admin users |

The frontend uses the existing FastAPI OAuth/session system. Browser OAuth callbacks redirect from the backend to `FRONTEND_URL + next_route` after the session cookie is set. Workspace activity calls the backend session-refresh endpoint on a five-minute throttle so active users receive sliding app-session renewal. A global TanStack Query/API-client auth handler clears local UI state and redirects to `/login?reason=session_expired` when the backend returns an expired/revoked 401. Do not add Auth.js/NextAuth for MVP auth.

## Design System

The visual source of truth is `backstage/design/`, especially `backstage/design/README.md`, `backstage/design/frontend_wireframe_implementation_plan.md`, and `backstage/design/source/colors_and_type.css`.

- Fonts are loaded locally in `src/app/layout.tsx`: Archivo, Sora, and Inter.
- Tailwind v4 tokens live in `src/app/globals.css` using `@theme`.
- Compact product typography utilities live in `src/app/globals.css`: `pb-page-title`, `pb-page-subtitle`, `pb-card-title`, `pb-ui-sm`, and `pb-ui-xs`.
- Use the semantic UI contract in `src/app/globals.css` before adding one-off Tailwind values:
  - Auth surfaces use `pb-auth-*` classes for headings, provider buttons, labels, controls, and footer copy.
  - Workspace geometry uses `pb-workspace-*` and `pb-chat-content` classes for rails, panels, and chat width.
  - Chat surfaces use `pb-chat-*` classes for empty-state titles, message body text, composer inputs, and user bubbles.
  - Dashboard/admin surfaces use `pb-dashboard-*`, `pb-admin-table-*`, `pb-admin-menu*`, and `pb-admin-nav-*` classes for dense text and control rhythm.
- Use `pb-focus-control` or `pb-focus-item` whenever an interactive element suppresses browser outlines. Do not add `outline-none` without an equivalent visible focus state.
- Repeated exact dimensions belong in Tailwind v4 `@theme` spacing tokens or named `pb-*` classes. Single-use arbitrary values are allowed only when they directly reflect the design handoff.
- Admin chrome uses shared globals such as `pb-admin-header-control`, `pb-admin-nav-item`, and `pb-admin-nav-icon` so Insights, Knowledge base, and Users & roles keep the same compact rhythm.
- Dense admin tables use shared globals such as `pb-admin-table-text`, `pb-admin-table-meta`, `pb-admin-table-action`, `pb-admin-menu`, and `pb-admin-menu-item`; avoid generic `text-sm`/`text-base` row controls that overpower table content.
- The palette is Playbook orange on warm charcoal. Avoid blue/purple AI gradients.
- Use local Playbook primitives in `src/components/ui/`.
- `Button`, `IconButton`, `Input`, `Textarea`, and Radix wrappers own default focus and sizing behavior. Use `Button size="sm"` as the canonical 36px compact app control for toolbar/header actions, and use `IconButton size="sm" variant="ghost"` for compact panel close/action buttons.
- `/login` and `/profile` live under the `src/app/(auth)/` route group, preserving their public URLs while sharing the auth layout, horizon background, warm vignette, and reduced-motion-safe stage. Their feature screens own only the raised auth card content.
- `/chat` and `/admin` live under the `src/app/(workspace)/` route group, preserving their public URLs while sharing the left/main/right workspace geometry through `WorkspaceShell`.
- Admin Insights is fixture-backed until Phase 4 analytics APIs land, but the UI renders the full Claude dashboard hierarchy: header controls, AI summary, topic/risk modules, query volume, and the analytics chat side panel.
- Admin pages share `AdminPageScaffold` for the Claude header, grid layer, toolbar band, content padding, and max-width rhythm across Insights, Knowledge base, and Users & roles.
- Super-admin Users & roles uses the design-backed table surface with search, role pills, locked current-user state, and Radix role-change menus wired to the existing admin user mutation.
- Radix powers accessible dialog, dropdown menu, tabs, tooltip, and switch behavior.
- Inline SVG is allowed only for the Playbook mark and SSO provider logos; use `lucide-react` for normal icons.

## Data And State

- Server state belongs in TanStack Query hooks in `src/hooks/`.
- API calls live in `src/lib/api/endpoints/` and use `apiClient`.
- `apiClient` sends cookie credentials, preserves multipart `FormData`, parses structured API errors, emits the shared auth-expired event for 401 session failures, and handles `204`.
- Athlete chat first-send uses `POST /api/v1/conversations`; follow-ups use
  `POST /api/v1/conversations/{conversation_id}/messages`. Both return
  `task_id` stream metadata, and the browser opens the returned SSE
  `stream_url` with cookies included.
- Zustand stores only client UI state, such as selected conversation, sources panel, admin tab, and settings modal state.
- Missing Phase 2+ APIs are represented by typed fixtures, not hidden server-state mocks.

## Structure

```text
src/app/                  App Router routes, grouped layouts, providers
src/components/ui/         Shared Playbook primitives
src/components/features/auth/ Shared auth/profile stage and card components
src/components/features/workspace/ Shared chat/admin workspace shell components
src/components/features/   Route/feature-specific components
src/hooks/                 TanStack Query hooks
src/lib/api/               Fetch client and endpoint modules
src/lib/fixtures/          Typed adapters for planned APIs
src/lib/store/             Zustand UI stores
src/lib/constants/         Route, query-key, and UI constants
src/lib/utils/             Pure helpers
src/types/                 Shared TypeScript contracts
```

## Testing

Use Vitest and React Testing Library. Components that use TanStack Query must be wrapped in a `QueryClientProvider`.

Core checks:

```bash
npm run typecheck
npm run lint
npm test
npm run build
```
