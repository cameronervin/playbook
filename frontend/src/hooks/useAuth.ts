import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getAuthProviders,
  getCurrentUser,
  logout,
  startOAuthLogin,
} from '@/src/lib/api/endpoints/auth'
import { QUERY_KEYS } from '@/src/lib/constants/config'

export const useAuthProviders = () =>
  useQuery({
    queryKey: [QUERY_KEYS.authProviders],
    queryFn: getAuthProviders,
  })

export const useCurrentUser = () =>
  useQuery({
    queryKey: [QUERY_KEYS.currentUser],
    queryFn: getCurrentUser,
    retry: false,
  })

export const useStartOAuthLogin = () =>
  useMutation({
    mutationFn: startOAuthLogin,
  })

export const useLogout = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: logout,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.currentUser] }),
  })
}
