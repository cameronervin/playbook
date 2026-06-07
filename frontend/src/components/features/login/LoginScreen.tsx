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

export function LoginScreen({ navigateAuthorizationUrl }: LoginScreenProps) {
  const { data, isLoading, isError } = useAuthProviders()
  const startOAuthLogin = useStartOAuthLogin()
  const navigate = navigateAuthorizationUrl ?? ((url: string) => window.location.assign(url))

  const providers = useMemo(() => {
    const byProvider = new Map(data?.providers.map((provider) => [provider.provider, provider]) ?? [])
    return PROVIDER_ORDER.map((provider) => byProvider.get(provider)).filter(
      (provider): provider is AuthProvider => Boolean(provider),
    )
  }, [data])

  const handleProviderClick = async (provider: AuthProvider) => {
    if (!provider.enabled) return
    const response = await startOAuthLogin.mutateAsync(provider.provider)
    navigate(response.authorization_url)
  }

  return (
    <main className="pb-stage relative flex min-h-dvh items-center justify-center overflow-hidden p-6">
      <HorizonBackground />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_45%,transparent,rgba(12,11,9,0.72)_62%)]" />
      <section className="animate-pb-rise relative z-10 w-full max-w-[380px] rounded-lg border border-border-strong bg-surface-raised px-8 pb-6 pt-16 text-center shadow-lg">
        <BrandLockup className="justify-center" />
        <h1 className="mt-9 text-lg font-semibold text-fg-1">Log in to continue</h1>
        <div className="mt-7 grid gap-3">
          {isLoading && <p className="text-sm text-fg-3">Checking available providers...</p>}
          {isError && <p className="text-sm text-danger">SSO providers are not available right now.</p>}
          {providers.map((provider) => (
            <button
              className="grid min-h-[52px] grid-cols-[50px_1fr] overflow-hidden rounded-md border border-border-strong bg-surface text-fg-1 transition hover:bg-surface-hover active:translate-y-px disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!provider.enabled || startOAuthLogin.isPending}
              key={provider.provider}
              onClick={() => handleProviderClick(provider)}
              type="button"
            >
              <span className="flex items-center justify-center border-r border-border bg-surface-raised">
                {providerLogo[provider.provider]}
              </span>
              <span className="flex items-center justify-center pr-[50px] text-base font-semibold">
                Continue with {provider.label}
              </span>
            </button>
          ))}
        </div>
        <footer className="mt-8 border-t border-border pt-5 text-xs text-fg-3">
          <a className="transition hover:text-fg-1" href="/privacy">Privacy Policy</a>
          <span className="px-2">.</span>
          <a className="transition hover:text-fg-1" href="/terms">Terms of Service</a>
        </footer>
      </section>
    </main>
  )
}
