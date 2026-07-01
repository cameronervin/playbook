export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export const API_VERSION = 'v1'

export const DEFAULT_PAGE_SIZE = 20

export const AUTH_PROVIDERS_STALE_TIME_MS = 30 * 60 * 1000

export const AUTH_PROVIDERS_GC_TIME_MS = 60 * 60 * 1000

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
  kbCollections: 'kbCollections',
  kbMetadataTags: 'kbMetadataTags',
  adminUsers: 'adminUsers',
  auditLogs: 'auditLogs',
  adminAnalyticsSummary: 'adminAnalyticsSummary',
  adminAnalyticsQueries: 'adminAnalyticsQueries',
  dashboardInsightCurrent: 'dashboardInsightCurrent',
  dashboardInsightRun: 'dashboardInsightRun',
  dashboardInsightOutputs: 'dashboardInsightOutputs',
  adminChatSessions: 'adminChatSessions',
  adminChatSessionDetail: 'adminChatSessionDetail',
} as const

export const UI_DIMENSIONS = {
  loginCardWidth: 380,
  chatNavWidth: 264,
  sourcesPanelWidth: 320,
  adminNavWidth: 272,
  composerMaxWidth: 760,
} as const
