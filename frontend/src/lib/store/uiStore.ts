import { create } from 'zustand'
import type { AdminChatMessageFixture, AdminTimeWindow, DashboardInsightStatus } from '@/src/types/fixtures'

type AdminTab = 'insights' | 'kb' | 'users'

interface UIState {
  activeConversationId: string | null
  sourcesOpen: boolean
  selectedCitationTitle: string | null
  settingsOpen: boolean
  adminTab: AdminTab
  adminChatOpen: boolean
  adminTimeWindow: AdminTimeWindow
  adminInsightStatus: DashboardInsightStatus
  adminChatMessages: AdminChatMessageFixture[]
  setActiveConversationId: (id: string | null) => void
  toggleSources: () => void
  setSourcesOpen: (open: boolean) => void
  setSelectedCitationTitle: (title: string | null) => void
  setSettingsOpen: (open: boolean) => void
  setAdminTab: (tab: AdminTab) => void
  setAdminChatOpen: (open: boolean) => void
  setAdminTimeWindow: (window: AdminTimeWindow) => void
  setAdminInsightStatus: (status: DashboardInsightStatus) => void
  addAdminChatMessage: (message: AdminChatMessageFixture) => void
  resetAdminChatMessages: () => void
}

export const useUIStore = create<UIState>((set) => ({
  activeConversationId: null,
  sourcesOpen: true,
  selectedCitationTitle: null,
  settingsOpen: false,
  adminTab: 'insights',
  adminChatOpen: false,
  adminTimeWindow: '7d',
  adminInsightStatus: 'completed',
  adminChatMessages: [],
  setActiveConversationId: (id) => set({ activeConversationId: id }),
  toggleSources: () => set((state) => ({ sourcesOpen: !state.sourcesOpen })),
  setSourcesOpen: (open) => set({ sourcesOpen: open }),
  setSelectedCitationTitle: (title) => set({ selectedCitationTitle: title, sourcesOpen: true }),
  setSettingsOpen: (open) => set({ settingsOpen: open }),
  setAdminTab: (tab) => set({ adminTab: tab }),
  setAdminChatOpen: (open) => set({ adminChatOpen: open }),
  setAdminTimeWindow: (window) => set({ adminTimeWindow: window }),
  setAdminInsightStatus: (status) => set({ adminInsightStatus: status }),
  addAdminChatMessage: (message) =>
    set((state) => ({ adminChatMessages: [...state.adminChatMessages, message] })),
  resetAdminChatMessages: () => set({ adminChatMessages: [] }),
}))
