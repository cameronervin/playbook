'use client'

import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'

export const DropdownMenu = DropdownMenuPrimitive.Root
export const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger

export const DropdownMenuContent = ({ children }: { children: React.ReactNode }) => (
  <DropdownMenuPrimitive.Portal>
    <DropdownMenuPrimitive.Content
      align="end"
      className="z-50 min-w-48 rounded-md border border-border-strong bg-surface-raised p-2 text-sm text-fg-2 shadow-md"
      sideOffset={8}
    >
      {children}
    </DropdownMenuPrimitive.Content>
  </DropdownMenuPrimitive.Portal>
)

export const DropdownMenuItem = DropdownMenuPrimitive.Item
