'use client'

import { useMemo } from 'react'
import { Code2 } from 'lucide-react'
import { AuthCard } from '@/src/components/features/auth/AuthLayout'
import { BrandLockup, GoogleLogo, MicrosoftLogo } from '@/src/components/ui'
import { useAuthProviders, useStartOAuthLogin } from '@/src/hooks/useAuth'
import type { AuthProvider } from '@/src/types/auth'

interface LoginScreenProps {
  navigateAuthorizationUrl?: (url: string) => void
  sessionExpired?: boolean
}

const PROVIDER_ORDER = ['microsoft', 'google', 'dev'] as const
const PROVIDER_SKELETON_ORDER = ['microsoft', 'google'] as const

const providerLogo = {
  microsoft: <MicrosoftLogo />,
  google: <GoogleLogo />,
  dev: <Code2 aria-hidden="true" className="h-5 w-5 text-fg-2" strokeWidth={1.8} />,
} as const

function AuthProviderSkeleton() {
  return (
    <div
      aria-hidden="true"
      className="pb-auth-provider-button"
      data-testid="auth-provider-skeleton"
    >
      <span className="pb-auth-provider-icon">
        <span className="h-5 w-5 rounded-sm bg-fg-4/40 motion-safe:animate-pulse" />
      </span>
      <span className="pb-auth-provider-label">
        <span className="h-4 w-[190px] max-w-[80%] rounded-sm bg-fg-4/35 motion-safe:animate-pulse" />
      </span>
    </div>
  )
}

export function LoginScreen({ navigateAuthorizationUrl, sessionExpired = false }: LoginScreenProps) {
  const { data, isError, isPending } = useAuthProviders()
  const startOAuthLogin = useStartOAuthLogin()
  const navigate = navigateAuthorizationUrl ?? ((url: string) => window.location.assign(url))

  const providers = useMemo(() => {
    const byProvider = new Map(data?.providers.map((provider) => [provider.provider, provider]) ?? [])
    return PROVIDER_ORDER.map((provider) => byProvider.get(provider)).filter(
      (provider): provider is AuthProvider => Boolean(provider),
    )
  }, [data])
  const hasProviders = providers.length > 0
  const showProviderSkeletons = isPending && !hasProviders
  const showProviderError = isError && !hasProviders

  const handleProviderClick = async (provider: AuthProvider) => {
    if (!provider.enabled) return
    const response = await startOAuthLogin.mutateAsync(provider.provider)
    navigate(response.authorization_url)
  }

  return (
    <AuthCard className="flex flex-col items-center text-center">
      <BrandLockup
        className="justify-center gap-[11px]"
        markSize={34}
        wordmarkClassName="pb-auth-wordmark"
      />
      <h1
        aria-label="Log in to continue"
        className="pb-auth-heading mt-6"
      >
        Log in to continue
      </h1>
      {sessionExpired && (
        <p className="pb-auth-copy mt-3 text-fg-2">
          Your session expired after a period of inactivity. Sign in again to continue.
        </p>
      )}
      <div className="mt-8 grid w-full gap-3">
        {showProviderSkeletons &&
          PROVIDER_SKELETON_ORDER.map((provider) => <AuthProviderSkeleton key={provider} />)}
        {showProviderError && <p className="pb-auth-copy text-danger">SSO providers are not available right now.</p>}
        {providers.map((provider) => (
          <button
            className="pb-auth-provider-button pb-focus-control"
            disabled={!provider.enabled || startOAuthLogin.isPending}
            key={provider.provider}
            onClick={() => handleProviderClick(provider)}
            type="button"
          >
            <span className="pb-auth-provider-icon">
              {providerLogo[provider.provider]}
            </span>
            <span className="pb-auth-provider-label">
              Continue with {provider.label}
            </span>
          </button>
        ))}
      </div>
      <footer className="pb-auth-footer mt-8 w-full border-t border-border pt-6">
        <a className="transition hover:text-fg-1" href="/privacy">Privacy Policy</a>
        <span className="px-2 text-fg-4">·</span>
        <a className="transition hover:text-fg-1" href="/terms">Terms of Service</a>
      </footer>
    </AuthCard>
  )
}
