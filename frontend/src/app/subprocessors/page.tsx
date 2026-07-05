import type { Metadata } from 'next'
import { LegalPage } from '@/src/components/features/legal/LegalPage'
import { LEGAL_PAGES } from '@/src/lib/legalContent'

export const metadata: Metadata = {
  title: 'Subprocessors | Playbook',
}

export default function SubprocessorsPage() {
  return <LegalPage page={LEGAL_PAGES.subprocessors} />
}
