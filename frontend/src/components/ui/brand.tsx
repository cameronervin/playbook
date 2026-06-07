import { cn } from '@/src/lib/utils/cn'

interface PlaybookMarkProps {
  className?: string
  size?: number
}

export function PlaybookMark({ className, size = 34 }: PlaybookMarkProps) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height={size}
      viewBox="0 0 512 512"
      width={size}
    >
      <path
        d="M32 402.84h68.86l68.86-119.46h207.41L480 104.18H342.28l-34.01 59.73h68.86l-34.85 59.73H135.7L32 402.84Z"
        fill="currentColor"
      />
      <path d="M204.56 104.18h68.03l-34.01 59.73h-68.86l34.84-59.73Z" fill="var(--brand)" />
      <path d="M291.67 321.54h68.03l-44.8 86.28h-65.54l42.31-86.28Z" fill="var(--brand)" />
    </svg>
  )
}

interface BrandLockupProps {
  className?: string
  markSize?: number
}

export function BrandLockup({ className, markSize = 34 }: BrandLockupProps) {
  return (
    <div className={cn('flex items-center gap-3 text-fg-1', className)}>
      <PlaybookMark size={markSize} />
      <span className="font-display text-2xl font-extrabold tracking-tight">Playbook</span>
    </div>
  )
}

export function MicrosoftLogo() {
  return (
    <svg aria-hidden="true" height="19" viewBox="0 0 23 23" width="19">
      <path d="M1 1h10v10H1z" fill="#f25022" />
      <path d="M12 1h10v10H12z" fill="#7fba00" />
      <path d="M1 12h10v10H1z" fill="#00a4ef" />
      <path d="M12 12h10v10H12z" fill="#ffb900" />
    </svg>
  )
}

export function GoogleLogo() {
  return (
    <svg aria-hidden="true" height="20" viewBox="0 0 48 48" width="20">
      <path
        d="M44.5 20H24v8.5h11.8C34.7 34 30 37.3 24 37.3c-7.3 0-13.3-6-13.3-13.3s6-13.3 13.3-13.3c3.2 0 6.2 1.1 8.5 3.2l6-6C34.6 4.2 29.6 2 24 2 11.8 2 2 11.8 2 24s9.8 22 22 22c11 0 21-8 21-22 0-1.3-.2-2.7-.5-4Z"
        fill="#4285f4"
      />
      <path d="M6.4 14.1 13.4 19.2c1.9-5 6-8.5 10.6-8.5 3.2 0 6.2 1.1 8.5 3.2l6-6C34.6 4.2 29.6 2 24 2 16.1 2 9.2 6.3 6.4 14.1Z" fill="#ea4335" />
      <path d="M24 46c5.5 0 10.2-1.8 13.8-5l-6.4-5.3c-2 1.3-4.5 2.1-7.4 2.1-5.9 0-10.9-4-12.7-9.4l-7 5.4C7.1 41 14.9 46 24 46Z" fill="#34a853" />
      <path d="M11.3 28.4a13.2 13.2 0 0 1 0-8.8l-7-5.5a22 22 0 0 0 0 19.8l7-5.5Z" fill="#fbbc05" />
    </svg>
  )
}
