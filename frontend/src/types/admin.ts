import type { CurrentUser, UserRole } from '@/src/types/auth'

export type AdminUser = CurrentUser

export interface UpdateUserRoleRequest {
  role: UserRole
}

export interface AuditLog {
  id: string
  organization_id: string
  actor_user_id: string | null
  action: string
  target_type: string
  target_id: string | null
  metadata: Record<string, unknown>
  created_at: string
}
