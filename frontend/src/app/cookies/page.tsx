import type { Metadata } from 'next'
import { LegalPage } from '@/src/components/features/legal/LegalPage'
import { LEGAL_PAGES } from '@/src/lib/legalContent'

export const metadata: Metadata = {
  title: 'Cookie Notice | Playbook',
}

export default function CookiesPage() {
  return <LegalPage page={LEGAL_PAGES.cookies} />
}
