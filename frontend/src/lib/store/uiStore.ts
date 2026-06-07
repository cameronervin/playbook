import { create } from 'zustand'

type AdminTab = 'insights' | 'kb' | 'users'

interface UIState {
  activeConversationId: string | null
  sourcesOpen: boolean
  selectedCitationTitle: string | null
  settingsOpen: boolean
  adminTab: AdminTab
  setActiveConversationId: (id: string | null) => void
  toggleSources: () => void
  setSourcesOpen: (open: boolean) => void
  setSelectedCitationTitle: (title: string | null) => void
  setSettingsOpen: (open: boolean) => void
  setAdminTab: (tab: AdminTab) => void
}

export const useUIStore = create<UIState>((set) => ({
  activeConversationId: null,
  sourcesOpen: true,
  selectedCitationTitle: null,
  settingsOpen: false,
  adminTab: 'insights',
  setActiveConversationId: (id) => set({ activeConversationId: id }),
  toggleSources: () => set((state) => ({ sourcesOpen: !state.sourcesOpen })),
  setSourcesOpen: (open) => set({ sourcesOpen: open }),
  setSelectedCitationTitle: (title) => set({ selectedCitationTitle: title, sourcesOpen: true }),
  setSettingsOpen: (open) => set({ settingsOpen: open }),
  setAdminTab: (tab) => set({ adminTab: tab }),
}))
