import type { Metadata } from 'next'
import { LegalPage } from '@/src/components/features/legal/LegalPage'
import { LEGAL_PAGES } from '@/src/lib/legalContent'

export const metadata: Metadata = {
  title: 'Privacy Policy | Playbook',
}

export default function PrivacyPage() {
  return <LegalPage page={LEGAL_PAGES.privacy} />
}
