import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listAdminUsers, listAuditLogs, updateAdminUserRole } from '@/src/lib/api/endpoints/admin'
import { QUERY_KEYS } from '@/src/lib/constants/config'

export const useAdminUsers = (enabled: boolean) =>
  useQuery({
    queryKey: [QUERY_KEYS.adminUsers],
    queryFn: listAdminUsers,
    enabled,
  })

export const useUpdateUserRole = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: 'athlete' | 'admin' | 'super_admin' }) =>
      updateAdminUserRole(userId, { role }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.adminUsers] }),
  })
}

export const useAuditLogs = (enabled: boolean) =>
  useQuery({
    queryKey: [QUERY_KEYS.auditLogs],
    queryFn: listAuditLogs,
    enabled,
  })
