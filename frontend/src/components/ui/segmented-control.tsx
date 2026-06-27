import { cn } from '@/src/lib/utils/cn'

interface SegmentedControlProps<TValue extends string> {
  value: TValue
  options: readonly TValue[]
  onChange: (value: TValue) => void
  label: string
}

export function SegmentedControl<TValue extends string>({
  value,
  options,
  onChange,
  label,
}: SegmentedControlProps<TValue>) {
  return (
    <div aria-label={label} className="inline-flex rounded-md bg-surface p-1" role="group">
      {options.map((option) => (
        <button
          className={cn(
            'pb-focus-control rounded-sm border border-transparent px-3 py-2 pb-ui-sm font-semibold text-fg-3 transition',
            value === option && 'bg-surface-raised text-brand',
          )}
          key={option}
          onClick={() => onChange(option)}
          type="button"
        >
          {option}
        </button>
      ))}
    </div>
  )
}
