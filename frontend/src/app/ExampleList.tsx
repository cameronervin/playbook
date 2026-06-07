'use client'

import { useExamples } from '@/src/hooks/useExample'
import { useExampleStore } from '@/src/lib/store/exampleStore'
import { cn } from '@/src/lib/utils/cn'

export function ExampleList() {
  const { data, isLoading, isError } = useExamples()
  const selectedExampleId = useExampleStore((state) => state.selectedExampleId)
  const setSelectedExampleId = useExampleStore((state) => state.setSelectedExampleId)

  if (isLoading) return <p className="text-sm text-gray-500">Loading examples…</p>
  if (isError) return <p className="text-sm text-gray-500">Failed to load examples.</p>
  if (!data || data.length === 0) return <p className="text-sm text-gray-500">No examples yet.</p>

  return (
    <ul className="flex flex-col gap-2">
      {data.map((example) => (
        <li key={example.id}>
          <button
            type="button"
            onClick={() => setSelectedExampleId(example.id)}
            className={cn(
              'w-full rounded-md border border-gray-200 p-4 text-left transition-colors hover:border-primary',
              selectedExampleId === example.id && 'border-primary bg-gray-100',
            )}
          >
            <span className="text-sm font-semibold text-gray-900">{example.name}</span>
            <span className="block text-xs text-gray-400">{example.status}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}
