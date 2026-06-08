'use client'

import * as TabsPrimitive from '@radix-ui/react-tabs'
import { cn } from '@/src/lib/utils/cn'

export const Tabs = TabsPrimitive.Root

export function TabsList({ children, className }: { children: React.ReactNode; className?: string }) {
  return <TabsPrimitive.List className={cn('flex gap-1 rounded-md bg-surface p-1', className)}>{children}</TabsPrimitive.List>
}

export function TabsTrigger({ value, children }: { value: string; children: React.ReactNode }) {
  return (
    <TabsPrimitive.Trigger
      className="rounded-sm px-4 py-2 text-sm font-semibold text-fg-3 transition data-[state=active]:bg-surface-raised data-[state=active]:text-brand"
      value={value}
    >
      {children}
    </TabsPrimitive.Trigger>
  )
}

export const TabsContent = TabsPrimitive.Content
