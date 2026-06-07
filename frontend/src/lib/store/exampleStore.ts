import { create } from 'zustand'

interface ExampleState {
  selectedExampleId: string | null
  setSelectedExampleId: (id: string | null) => void
  clearSelection: () => void
}

/**
 * Client-side UI state for examples.
 * Server data lives in TanStack Query — keep only ephemeral UI state here.
 */
export const useExampleStore = create<ExampleState>((set) => ({
  selectedExampleId: null,
  setSelectedExampleId: (id) => set({ selectedExampleId: id }),
  clearSelection: () => set({ selectedExampleId: null }),
}))
