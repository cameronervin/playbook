'use client'

import { PanelRightClose, PanelRightOpen } from 'lucide-react'
import { IconButton } from '@/src/components/ui'

interface ChatTopBarProps {
  sourcesOpen: boolean
  title: string
  onToggleSources: () => void
}

export function ChatTopBar({ sourcesOpen, title, onToggleSources }: ChatTopBarProps) {
  return (
    <header
      aria-label="Chat actions"
      className="relative z-10 flex h-16 shrink-0 items-center gap-3 border-b border-border bg-bg-base px-[22px]"
      role="banner"
    >
      <div className="min-w-0">
        <h1 className="pb-panel-title truncate">{title}</h1>
      </div>
      <div className="ml-auto">
        <IconButton aria-label="Toggle sources" onClick={onToggleSources}>
          {sourcesOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
        </IconButton>
      </div>
    </header>
  )
}
