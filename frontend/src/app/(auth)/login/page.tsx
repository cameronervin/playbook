import { LoginScreen } from '@/src/components/features/login/LoginScreen'

interface LoginPageProps {
  searchParams?: Promise<Record<string, string | string[] | undefined>>
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = await searchParams
  return <LoginScreen sessionExpired={params?.reason === 'session_expired'} />
}
