import { apiClient } from '@/src/lib/api/client'
import { API_VERSION } from '@/src/lib/constants/config'
import type {
  AuthProvidersResponse,
  CurrentUser,
  LogoutResponse,
  OAuthLoginResponse,
  UpdateProfileRequest,
  UpdateProfileResponse,
} from '@/src/types/auth'

const AUTH_PATH = `/api/${API_VERSION}/auth`
const USERS_PATH = `/api/${API_VERSION}/users`

export const getAuthProviders = (): Promise<AuthProvidersResponse> =>
  apiClient<AuthProvidersResponse>(`${AUTH_PATH}/providers`)

export const startOAuthLogin = (provider: string): Promise<OAuthLoginResponse> =>
  apiClient<OAuthLoginResponse>(`${AUTH_PATH}/${provider}/login`)

export const logout = (): Promise<LogoutResponse> =>
  apiClient<LogoutResponse>(`${AUTH_PATH}/logout`, { method: 'POST' })

export const getCurrentUser = (): Promise<CurrentUser> =>
  apiClient<CurrentUser>(`${USERS_PATH}/me`)

export const updateProfile = (
  request: UpdateProfileRequest,
): Promise<UpdateProfileResponse> =>
  apiClient<UpdateProfileResponse>(`${USERS_PATH}/me/profile`, {
    method: 'PATCH',
    json: request,
  })
