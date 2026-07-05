'use client'

import * as TabsPrimitive from '@radix-ui/react-tabs'
import type { ReactNode } from 'react'
import { cn } from '@/src/lib/utils/cn'

export const Tabs = TabsPrimitive.Root

export function TabsList({ children, className }: { children: ReactNode; className?: string }) {
  return <TabsPrimitive.List className={cn('flex gap-1 rounded-md bg-surface p-1', className)}>{children}</TabsPrimitive.List>
}

export function TabsTrigger({ value, children, className }: { value: string; children: ReactNode; className?: string }) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        'pb-focus-control rounded-sm border border-transparent px-4 py-2 pb-ui-sm font-semibold text-fg-3 transition data-[state=active]:bg-surface-raised data-[state=active]:text-brand',
        className,
      )}
      value={value}
    >
      {children}
    </TabsPrimitive.Trigger>
  )
}

export const TabsContent = TabsPrimitive.Content
