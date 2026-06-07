import { useMutation, useQueryClient } from '@tanstack/react-query'
import { updateProfile } from '@/src/lib/api/endpoints/auth'
import { QUERY_KEYS } from '@/src/lib/constants/config'

export const useUpdateProfile = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: updateProfile,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.currentUser] }),
  })
}
