import type { Metadata } from 'next'
import { LegalPage } from '@/src/components/features/legal/LegalPage'
import { LEGAL_PAGES } from '@/src/lib/legalContent'

export const metadata: Metadata = {
  title: 'Security | Playbook',
}

export default function SecurityPage() {
  return <LegalPage page={LEGAL_PAGES.security} />
}
