'use client'

import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import type { ComponentPropsWithoutRef, ReactNode } from 'react'
import { cn } from '@/src/lib/utils/cn'

export const DropdownMenu = DropdownMenuPrimitive.Root
export const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger

interface DropdownMenuContentProps extends ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content> {
  children: ReactNode
}

export function DropdownMenuContent({
  align = 'end',
  children,
  className,
  sideOffset = 8,
  ...props
}: DropdownMenuContentProps) {
  return (
  <DropdownMenuPrimitive.Portal>
    <DropdownMenuPrimitive.Content
      align={align}
      className={cn('pb-menu-content', className)}
      sideOffset={sideOffset}
      {...props}
    >
      {children}
    </DropdownMenuPrimitive.Content>
  </DropdownMenuPrimitive.Portal>
  )
}

interface DropdownMenuItemProps extends ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item> {
  danger?: boolean
}

export function DropdownMenuItem({ className, danger = false, ...props }: DropdownMenuItemProps) {
  return (
    <DropdownMenuPrimitive.Item
      className={cn('pb-menu-item pb-focus-item', danger && 'text-danger focus:bg-danger-bg focus:text-danger', className)}
      {...props}
    />
  )
}
