# Frontend

A reusable Next.js (App Router) frontend skeleton: **Next.js 15 + React 19 + Tailwind CSS v4 + TanStack Query + Zustand**, TypeScript strict throughout.

## Getting started

```bash
npm install
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL
npm run dev                          # http://localhost:3000
```

Scripts:

| Script | Purpose |
|--------|---------|
| `npm run dev` | Start the dev server |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run lint` | ESLint (eslint-config-next) |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run test` | Vitest unit tests |

## App Router conventions: server vs client components

This project uses the Next.js **App Router** (the `src/app/` directory).

- **Server Components are the default.** Every file under `src/app/` runs on the server unless it opts in to the client. Server components can be `async`, read data directly, and ship zero JS to the browser. Keep pages and layouts as server components where possible.
- **Client Components opt in with `'use client'`** as the first line of the file. You need this whenever you use React hooks (`useState`, `useEffect`), browser APIs, event handlers, or client libraries like TanStack Query and Zustand.
- **Pattern:** keep the page a server component and push interactivity into a small `'use client'` child. See `src/app/page.tsx` (server) rendering `src/app/ExampleList.tsx` (client, uses the data hook + store).
- **Route files** (`layout.tsx`, `page.tsx`) use **default exports** — this is required by Next.js. Everything else uses **named exports**.

## Tailwind CSS v4 — design tokens via `@theme`

Tailwind v4 is configured without a `tailwind.config.js` for tokens:

- `postcss.config.mjs` registers `@tailwindcss/postcss`.
- `src/app/globals.css` starts with `@import "tailwindcss";`.
- Design tokens are declared in a `@theme { ... }` block in `src/app/globals.css`. Tailwind generates matching utilities automatically — e.g. `--color-primary` → `text-primary` / `bg-primary`, `--radius-md` → `rounded-md`.

**Rules:**

- Always use token-backed utilities. **No arbitrary values** (`text-[13px]`, `bg-[#abc]`, `p-[7px]`). If a value is missing, add it to the `@theme` block as a named token.
- One value = one token. Don't create duplicate tokens for the same value.
- Use `cn()` (`src/lib/utils/cn.ts`, clsx + tailwind-merge) for all conditional classes — never string-concatenate class names.

Replace the neutral tokens in `globals.css` with your design system.

## Where things live

```
src/app/                  Routes, layouts, pages (server components by default)
  layout.tsx              Root layout: wraps children in <Providers>
  providers.tsx           'use client': QueryClientProvider
  page.tsx                Home route (server component)
  ExampleList.tsx         'use client' child consuming the data hook + store
src/components/
  ui/                     Reusable, stateless UI primitives
  features/               Feature-specific components
src/lib/
  api/client.ts           Typed fetch wrapper (apiClient)
  api/endpoints/          One file per API domain
  store/                  Zustand stores
  constants/              Named constants / config (no magic values in components)
  utils/                  Pure utility functions (no hooks, no JSX)
src/hooks/                App-wide shared hooks (TanStack Query hooks)
src/types/                Global TypeScript interfaces
```

## State management

- **Server state → TanStack Query.** All data fetching goes through a query/mutation hook in `src/hooks/` that calls an endpoint in `src/lib/api/endpoints/`. Never fetch in a component body or `useEffect`. See `src/hooks/useExample.ts`.
- **Client state → Zustand.** Ephemeral UI state (selections, toggles, modals) lives in a store under `src/lib/store/`. Don't store server data here. See `src/lib/store/exampleStore.ts`.

## How to add things

**A page/route:** create `src/app/<route>/page.tsx` (server component). If it needs interactivity, render a small `'use client'` child component.

**A feature:** create feature-specific components under `src/components/features/<feature>/`. Reusable primitives used by 2+ features go in `src/components/ui/`.

**An API endpoint:**
1. Add/extend the type in `src/types/<domain>.ts`.
2. Add a function in `src/lib/api/endpoints/<domain>.ts` that calls `apiClient<T>(...)`.
3. Add a TanStack Query hook in `src/hooks/use<Domain>.ts`.
4. Register the query key in `src/lib/constants/config.ts`.

## Testing — Vitest + React Testing Library

- Config: `vitest.config.ts` (jsdom environment, `@` alias, globals enabled).
- Setup: `vitest.setup.ts` registers `@testing-library/jest-dom` matchers.
- Co-locate tests as `*.test.tsx` / `*.test.ts`. Components that use TanStack Query must be wrapped in a `QueryClientProvider` in the test — see `src/app/page.test.tsx`.
- Run with `npm run test`.

## Code conventions

- TypeScript **strict**, no `any`.
- Component props typed with `interface XxxProps {}`.
- **Named exports** everywhere except Next.js route files (`page.tsx`/`layout.tsx`).
- Functional components only.
- Use the current `@/src/...` import convention for internal frontend imports.
- ES6+: arrow functions, destructuring, template literals, `?.`, `??`.
