export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export const API_VERSION = 'v1'

export const DEFAULT_PAGE_SIZE = 20

export const ROUTES = {
  root: '/',
  login: '/login',
  profile: '/profile',
  chat: '/chat',
  admin: '/admin',
} as const

export const QUERY_KEYS = {
  authProviders: 'authProviders',
  currentUser: 'currentUser',
  conversations: 'conversations',
  conversationDetail: 'conversationDetail',
  kbDocuments: 'kbDocuments',
  adminUsers: 'adminUsers',
  auditLogs: 'auditLogs',
} as const

export const UI_DIMENSIONS = {
  loginCardWidth: 380,
  chatNavWidth: 300,
  sourcesPanelWidth: 340,
  adminNavWidth: 272,
  composerMaxWidth: 760,
} as const
