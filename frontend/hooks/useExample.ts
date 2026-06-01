import { useQuery } from '@tanstack/react-query'
import { getExamples } from '@/lib/api/endpoints/example'
import { QUERY_KEYS } from '@/lib/constants/config'
import type { Example } from '@/types/example'

/**
 * Fetch the list of examples via TanStack Query.
 */
export function useExamples() {
  return useQuery<Example[]>({
    queryKey: [QUERY_KEYS.examples],
    queryFn: getExamples,
  })
}
