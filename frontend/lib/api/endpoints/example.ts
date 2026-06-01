import { apiClient } from '@/lib/api/client'
import { API_VERSION } from '@/lib/constants/config'
import type { Example } from '@/types/example'

const BASE_PATH = `/api/${API_VERSION}/examples`

export async function getExamples(): Promise<Example[]> {
  return apiClient<Example[]>(BASE_PATH)
}

export async function getExample(id: string): Promise<Example> {
  return apiClient<Example>(`${BASE_PATH}/${id}`)
}
