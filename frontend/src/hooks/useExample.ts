import { useQuery } from '@tanstack/react-query'
import { getExamples } from '@/src/lib/api/endpoints/example'
import { QUERY_KEYS } from '@/src/lib/constants/config'
import type { Example } from '@/src/types/example'

/**
 * Fetch the list of examples via TanStack Query.
 */
export function useExamples() {
  return useQuery<Example[]>({
    queryKey: [QUERY_KEYS.examples],
    queryFn: getExamples,
  })
}
