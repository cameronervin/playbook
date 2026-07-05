import { ROUTES } from '@/src/lib/constants/config'
import type { CurrentUser, UserRole } from '@/src/types/auth'

type RouteUser = Pick<CurrentUser, 'profile_complete' | 'role'>

export function isAdminRole(role: UserRole): boolean {
  return role === 'admin' || role === 'super_admin'
}

export function getDefaultAuthenticatedRoute(user: RouteUser): string {
  if (user.role === 'athlete' && !user.profile_complete) return ROUTES.profile
  return isAdminRole(user.role) ? ROUTES.admin : ROUTES.chat
}

export function getChatWorkspaceRedirect(user: RouteUser): string | null {
  if (user.role === 'athlete' && !user.profile_complete) return ROUTES.profile
  return null
}
