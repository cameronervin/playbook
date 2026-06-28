export type UserRole = 'athlete' | 'admin' | 'super_admin'
export type AuthProviderName = 'google' | 'microsoft' | 'dev'
export type DevAuthPersona = 'athlete' | 'new_athlete' | 'admin' | 'super_admin'

export interface CurrentUser {
  id: string
  organization_id: string
  email: string
  name: string
  role: UserRole
  sport_team?: string | null
  profile_complete: boolean
  is_active: boolean
  created_at?: string | null
}

export interface AuthProvider {
  provider: AuthProviderName
  label: string
  enabled: boolean
  login_url: string
}

export interface AuthProvidersResponse {
  providers: AuthProvider[]
}

export interface OAuthLoginResponse {
  authorization_url: string
}

export interface OAuthLoginRequest {
  provider: AuthProviderName
  persona?: DevAuthPersona
}

export interface UpdateProfileRequest {
  name: string
  sport_team: string
  selected_role: 'athlete'
}

export interface UpdateProfileResponse extends CurrentUser {
  next_route: string
}

export interface LogoutResponse {
  status: 'ok'
}
