# Next.js Rules (App Router + TypeScript)

## Layers
```
src/app/ (routes, layouts) -> src/components/ -> src/hooks/ -> src/lib/store/ (state)
```

## Server vs Client Components
- **Server Components are the default.** No directive needed. Use them for data fetching, layouts, and static content. They run on the server and ship zero JS.
- Add `'use client'` at the **top of the file** only when you need: state (`useState`), effects (`useEffect`), event handlers, browser APIs, or client-only libraries (TanStack Query, Zustand).
- Keep `'use client'` at the **leaves** of the tree — push interactivity down so most of the tree stays server-rendered.
- Fetch data in Server Components (`async` components, direct `await`) where possible; use TanStack Query in Client Components for cached/refetched client state.

## DO
- Functional components only
- Type all props with `interface Props {}`
- Server Components by default; `'use client'` only when needed
- TanStack Query for client-side server state (fetch, cache, refetch)
- Zustand for client UI state (auth, panels, toggles)
- Custom hooks to encapsulate client logic (must be in `'use client'` files)
- `cn()` for conditional classes
- Co-locate routes in `src/app/`; use `layout.tsx`, `page.tsx`, `loading.tsx`, `error.tsx`

## DON'T
- Use `any` type
- Put `'use client'` at the root of the tree
- Call hooks (`useState`/`useEffect`) in a Server Component
- Fetch in a component body with `useEffect` (use Server Component `await` or TanStack Query)
- Store server data in Zustand (use TanStack Query)
- Prop drill > 2 levels (use context or store)
- Import server-only code into a Client Component

## Anti-Patterns
| Smell | Fix |
|-------|-----|
| `any` type | Define interface |
| `useEffect` for data | Server Component `await` or TanStack Query |
| `'use client'` at root | Move it to the interactive leaf |
| Hooks in Server Component | Mark file `'use client'` or extract |
| Giant component | Split by responsibility |
| Props > 5 | Compose or use context |

## Examples
```tsx
// Server Component (default) - src/app/items/page.tsx
import { getItems } from '@/src/lib/api/items'
import { ItemList } from '@/src/components/features/items/ItemList'

export default async function ItemsPage() {
  const items = await getItems()
  return <ItemList items={items} />
}
```

```tsx
// Client Component — needs interactivity
'use client'

import { useQuery } from '@tanstack/react-query'
import { api } from '@/src/lib/api/client'

interface Props { id: string }

export function Item({ id }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ['item', id],
    queryFn: () => api.getItem(id),
  })
  if (isLoading) return <Spinner />
  return <Card>{data.name}</Card>
}
```
