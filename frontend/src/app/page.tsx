import { ExampleList } from '@/src/app/ExampleList'

export default function HomePage() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold text-gray-900">Agentic App Scaffold</h1>
        <p className="text-sm text-gray-500">
          Next.js App Router + Tailwind v4 + TanStack Query + Zustand.
        </p>
      </header>
      <ExampleList />
    </main>
  )
}
