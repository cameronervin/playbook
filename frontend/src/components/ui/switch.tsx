'use client'

import * as SwitchPrimitive from '@radix-ui/react-switch'

interface SwitchProps {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  label: string
}

export function Switch({ checked, onCheckedChange, label }: SwitchProps) {
  return (
    <label className="flex items-center justify-between gap-4 text-sm text-fg-2">
      <span>{label}</span>
      <SwitchPrimitive.Root
        checked={checked}
        className="h-6 w-11 rounded-pill border border-border-strong bg-surface data-[state=checked]:bg-brand"
        onCheckedChange={onCheckedChange}
      >
        <SwitchPrimitive.Thumb className="block h-5 w-5 translate-x-0.5 rounded-pill bg-fg-1 transition data-[state=checked]:translate-x-5 data-[state=checked]:bg-fg-on-brand" />
      </SwitchPrimitive.Root>
    </label>
  )
}
