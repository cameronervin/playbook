import type { Metadata } from 'next'
import localFont from 'next/font/local'
import { Providers } from '@/src/app/providers'
import { cn } from '@/src/lib/utils/cn'
import './globals.css'

const archivo = localFont({
  src: [
    { path: './fonts/Archivo-Variable.ttf', style: 'normal', weight: '100 900' },
    { path: './fonts/Archivo-Italic-Variable.ttf', style: 'italic', weight: '100 900' },
  ],
  variable: '--font-archivo',
  display: 'swap',
})

const sora = localFont({
  src: './fonts/Sora-Variable.ttf',
  variable: '--font-sora',
  display: 'swap',
})

const inter = localFont({
  src: './fonts/Inter-Variable.ttf',
  variable: '--font-inter',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Playbook',
  description: 'Chat-first support for college athletic departments.',
}

interface RootLayoutProps {
  children: React.ReactNode
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" className={cn(archivo.variable, sora.variable, inter.variable)}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
