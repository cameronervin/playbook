import type { Metadata } from 'next'
import { Providers } from '@/src/app/providers'
import '@/app/globals.css'

export const metadata: Metadata = {
  title: 'Agentic App Scaffold',
  description: 'A reusable Next.js App Router frontend scaffold.',
}

interface RootLayoutProps {
  children: React.ReactNode
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
