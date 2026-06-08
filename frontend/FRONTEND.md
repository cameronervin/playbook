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

The frontend uses the existing FastAPI OAuth/session system. Browser OAuth callbacks redirect from the backend to `FRONTEND_URL + next_route` after the session cookie is set. Do not add Auth.js/NextAuth for MVP auth.

## Design System

The visual source of truth is `docs/design/`, especially `docs/design/README.md`, `docs/design/frontend_wireframe_implementation_plan.md`, and `docs/design/source/colors_and_type.css`.

- Fonts are loaded locally in `src/app/layout.tsx`: Archivo, Sora, and Inter.
- Tailwind v4 tokens live in `src/app/globals.css` using `@theme`.
- The palette is Playbook orange on warm charcoal. Avoid blue/purple AI gradients.
- Use local Playbook primitives in `src/components/ui/`.
- Radix powers accessible dialog, dropdown menu, tabs, tooltip, and switch behavior.
- Inline SVG is allowed only for the Playbook mark and SSO provider logos; use `lucide-react` for normal icons.

## Data And State

- Server state belongs in TanStack Query hooks in `src/hooks/`.
- API calls live in `src/lib/api/endpoints/` and use `apiClient`.
- `apiClient` sends cookie credentials, preserves multipart `FormData`, parses structured API errors, and handles `204`.
- Zustand stores only client UI state, such as selected conversation, sources panel, admin tab, and settings modal state.
- Missing Phase 2+ APIs are represented by typed fixtures, not hidden server-state mocks.

## Structure

```text
src/app/                  App Router routes, layout, providers
src/components/ui/         Shared Playbook primitives
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
