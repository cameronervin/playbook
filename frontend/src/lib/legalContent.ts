import { ROUTES } from '@/src/lib/constants/config'

export type LegalSlug = 'privacy' | 'terms' | 'cookies' | 'subprocessors' | 'security'

export interface LegalContentSection {
  body: string[]
  heading: string
}

export interface LegalPageContent {
  sections: LegalContentSection[]
  slug: LegalSlug
  summary: string
  title: string
  updatedAt: string
}

export interface LegalNavLink {
  href: string
  label: string
  slug: LegalSlug
}

export const LEGAL_LAST_UPDATED = 'July 2, 2026'

export const SECURITY_CONTACT_EMAIL = 'security@playbook.example'

export const LEGAL_NAV_LINKS: LegalNavLink[] = [
  { href: ROUTES.privacy, label: 'Privacy Policy', slug: 'privacy' },
  { href: ROUTES.terms, label: 'Terms of Service', slug: 'terms' },
  { href: ROUTES.cookies, label: 'Cookie Notice', slug: 'cookies' },
  { href: ROUTES.subprocessors, label: 'Subprocessors', slug: 'subprocessors' },
  { href: ROUTES.security, label: 'Security', slug: 'security' },
]

export const LEGAL_PAGES: Record<LegalSlug, LegalPageContent> = {
  privacy: {
    slug: 'privacy',
    title: 'Privacy Policy',
    updatedAt: LEGAL_LAST_UPDATED,
    summary:
      'How Playbook handles account, profile, chat, upload, and usage data for department support workflows.',
    sections: [
      {
        heading: 'Information we process',
        body: [
          'Playbook processes SSO account details, profile fields, chat messages, citations, uploaded files, and usage events needed to provide the product.',
          'Department administrators may upload approved knowledge-base documents. Athlete conversation files stay scoped to the conversation unless a later approved workflow says otherwise.',
        ],
      },
      {
        heading: 'How information is used',
        body: [
          'We use information to authenticate users, route support, ground agent answers, maintain safety boundaries, troubleshoot product issues, and provide admin analytics.',
          'Analytics should be presented with the least identifying detail needed for the department workflow.',
        ],
      },
      {
        heading: 'Control and review',
        body: [
          'Your department controls which users have access and which documents are approved for Playbook.',
          'Review this content with counsel before production launch and replace placeholders with the final department-approved privacy terms.',
        ],
      },
    ],
  },
  terms: {
    slug: 'terms',
    title: 'Terms of Service',
    updatedAt: LEGAL_LAST_UPDATED,
    summary:
      'Use Playbook for department support workflows, with human review for decisions that affect athletes or staff.',
    sections: [
      {
        heading: 'Permitted use',
        body: [
          'Use Playbook for athletics department support, knowledge discovery, and administrative workflows authorized by your organization.',
          'Do not upload secrets, unrelated personal data, or content your department has not approved for the intended audience.',
        ],
      },
      {
        heading: 'AI output',
        body: [
          'Playbook responses are AI generated and may be incomplete or incorrect. Review answers before relying on them for decisions.',
          'Medical, legal, mental-health, emergency, harassment, recruiting-risk, and individualized financial questions should be escalated to the appropriate department channel.',
        ],
      },
      {
        heading: 'Prototype terms',
        body: [
          'These terms are product UI placeholders for pilot work.',
          'Review this content with counsel before production launch and replace placeholders with the final terms for your organization.',
        ],
      },
    ],
  },
  cookies: {
    slug: 'cookies',
    title: 'Cookie Notice',
    updatedAt: LEGAL_LAST_UPDATED,
    summary:
      'How Playbook uses essential browser storage for authentication, security, and product operation.',
    sections: [
      {
        heading: 'Essential cookies',
        body: [
          'Playbook uses essential cookies and browser storage to keep users signed in, protect sessions, remember local interface state, and support product security.',
          'These controls are required for the app to work and are not used for third-party advertising in this prototype.',
        ],
      },
      {
        heading: 'Local settings',
        body: [
          'Some interface preferences may be stored locally in the browser so the workspace behaves consistently between visits.',
          'Clearing browser data may reset these local preferences or require a fresh sign-in.',
        ],
      },
      {
        heading: 'Updates',
        body: [
          'If production analytics, support, or marketing cookies are added later, this page should be updated before launch.',
          'Review this content with counsel before production launch.',
        ],
      },
    ],
  },
  subprocessors: {
    slug: 'subprocessors',
    title: 'Subprocessors',
    updatedAt: LEGAL_LAST_UPDATED,
    summary:
      'A production subprocessor register should name the vendors used to operate Playbook.',
    sections: [
      {
        heading: 'Current register',
        body: [
          'This prototype does not publish a final production vendor list.',
          'Before launch, replace this page with the approved subprocessors for hosting, storage, authentication, AI models, embeddings, observability, and support operations.',
        ],
      },
      {
        heading: 'Expected categories',
        body: [
          'Playbook may rely on cloud hosting, object storage, database services, SSO identity providers, LLM and embedding providers, monitoring, and support tooling.',
          'Only approved vendors should process department or athlete data.',
        ],
      },
      {
        heading: 'Change notice',
        body: [
          'Production deployments should document how departments are notified when subprocessors change.',
          'Review this content with counsel before production launch.',
        ],
      },
    ],
  },
  security: {
    slug: 'security',
    title: 'Security',
    updatedAt: LEGAL_LAST_UPDATED,
    summary:
      'How Playbook approaches account security, data handling, uploads, and vulnerability reporting.',
    sections: [
      {
        heading: 'Security posture',
        body: [
          'Playbook uses SSO-backed authentication, role-based workspace access, scoped uploads, structured API boundaries, and server-side validation.',
          'Production deployments should run over HTTPS, store secrets outside source code, and restrict access by organization and role.',
        ],
      },
      {
        heading: 'Uploads and data handling',
        body: [
          'Conversation uploads are scoped to the active conversation. Admin knowledge-base uploads should be department-approved before they can ground athlete answers.',
          'Users should not upload passwords, tokens, payment data, or unrelated personal data.',
        ],
      },
      {
        heading: 'Vulnerability reports',
        body: [
          `Send security reports to ${SECURITY_CONTACT_EMAIL}. This address is a placeholder until a production security mailbox is approved.`,
          'Review this content with counsel and security owners before production launch.',
        ],
      },
    ],
  },
}

export const SECURITY_TXT = [
  `Contact: mailto:${SECURITY_CONTACT_EMAIL}`,
  'Policy: /security',
  'Preferred-Languages: en',
  'Canonical: /.well-known/security.txt',
  'Expires: 2027-07-02T00:00:00.000Z',
  '',
].join('\n')
