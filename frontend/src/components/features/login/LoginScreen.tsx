'use client'

import { useMemo } from 'react'
import { HorizonBackground } from '@/src/components/features/common/HorizonBackground'
import { BrandLockup, GoogleLogo, MicrosoftLogo } from '@/src/components/ui'
import { useAuthProviders, useStartOAuthLogin } from '@/src/hooks/useAuth'
import type { AuthProvider } from '@/src/types/auth'

interface LoginScreenProps {
  navigateAuthorizationUrl?: (url: string) => void
}

const PROVIDER_ORDER = ['microsoft', 'google'] as const

const providerLogo = {
  microsoft: <MicrosoftLogo />,
  google: <GoogleLogo />,
} as const

function AuthProviderSkeleton() {
  return (
    <div
      aria-hidden="true"
      className="grid min-h-[52px] w-full grid-cols-[50px_1fr] overflow-hidden rounded-md border border-border-strong bg-surface"
      data-testid="auth-provider-skeleton"
    >
      <span className="flex items-center justify-center border-r border-border bg-surface-raised">
        <span className="h-5 w-5 rounded-sm bg-fg-4/40 motion-safe:animate-pulse" />
      </span>
      <span className="flex items-center justify-center py-[15px] pr-[50px]">
        <span className="h-4 w-[190px] max-w-[80%] rounded-sm bg-fg-4/35 motion-safe:animate-pulse" />
      </span>
    </div>
  )
}

export function LoginScreen({ navigateAuthorizationUrl }: LoginScreenProps) {
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
    <main className="pb-login-stage" data-testid="login-stage">
      <HorizonBackground />
      <section className="animate-pb-rise relative z-10 flex w-full max-w-[380px] flex-col items-center rounded-lg border border-border-strong bg-surface-raised px-8 pb-6 pt-16 text-center shadow-lg">
        <BrandLockup
          className="justify-center gap-[11px]"
          markSize={34}
          wordmarkClassName="text-[26px] leading-none tracking-normal"
        />
        <h1
          aria-label="Log in to continue"
          className="mt-6 font-display text-lg font-bold uppercase leading-[1.2] tracking-normal text-fg-1"
        >
          LOG IN TO CONTINUE
        </h1>
        <div className="mt-8 grid w-full gap-3">
          {showProviderSkeletons && PROVIDER_ORDER.map((provider) => <AuthProviderSkeleton key={provider} />)}
          {showProviderError && <p className="text-sm text-danger">SSO providers are not available right now.</p>}
          {providers.map((provider) => (
            <button
              className="grid min-h-[52px] w-full grid-cols-[50px_1fr] overflow-hidden rounded-md border border-border-strong bg-surface font-body text-base font-semibold text-fg-1 transition hover:bg-surface-hover focus-visible:border-border-brand active:translate-y-px disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!provider.enabled || startOAuthLogin.isPending}
              key={provider.provider}
              onClick={() => handleProviderClick(provider)}
              type="button"
            >
              <span className="flex items-center justify-center border-r border-border bg-surface-raised">
                {providerLogo[provider.provider]}
              </span>
              <span className="flex items-center justify-center py-[15px] pr-[50px]">
                Continue with {provider.label}
              </span>
            </button>
          ))}
        </div>
        <footer className="mt-8 w-full border-t border-border pt-6 text-xs text-fg-3">
          <a className="transition hover:text-fg-1" href="/privacy">Privacy Policy</a>
          <span className="px-2 text-fg-4">·</span>
          <a className="transition hover:text-fg-1" href="/terms">Terms of Service</a>
        </footer>
      </section>
    </main>
  )
}
