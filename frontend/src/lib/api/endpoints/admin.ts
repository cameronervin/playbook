import { apiClient } from '@/src/lib/api/client'
import { API_VERSION } from '@/src/lib/constants/config'
import type { AdminUser, AuditLog, UpdateUserRoleRequest } from '@/src/types/admin'

const ADMIN_PATH = `/api/${API_VERSION}/admin`

export const listAdminUsers = (): Promise<AdminUser[]> =>
  apiClient<AdminUser[]>(`${ADMIN_PATH}/users`)

export const updateAdminUserRole = (
  userId: string,
  request: UpdateUserRoleRequest,
): Promise<AdminUser> =>
  apiClient<AdminUser>(`${ADMIN_PATH}/users/${userId}/role`, {
    method: 'PATCH',
    json: request,
  })

export const listAuditLogs = (): Promise<AuditLog[]> =>
  apiClient<AuditLog[]>(`${ADMIN_PATH}/audit-logs`)
