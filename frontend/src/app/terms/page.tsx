import type { Metadata } from 'next'
import { LegalPage } from '@/src/components/features/legal/LegalPage'
import { LEGAL_PAGES } from '@/src/lib/legalContent'

export const metadata: Metadata = {
  title: 'Terms of Service | Playbook',
}

export default function TermsPage() {
  return <LegalPage page={LEGAL_PAGES.terms} />
}
