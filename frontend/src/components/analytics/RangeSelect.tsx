import { Button } from '@/components/ui/button'
import type { AnalyticsRange } from '@/types/analytics'

const RANGES: AnalyticsRange[] = [7, 30, 90]

interface RangeSelectProps {
  value: AnalyticsRange
  onChange: (days: AnalyticsRange) => void
}

export function RangeSelect({ value, onChange }: RangeSelectProps) {
  return (
    <div role="group" aria-label="Date range" className="flex gap-2">
      {RANGES.map((d) => (
        <Button
          key={d}
          size="sm"
          variant={d === value ? 'default' : 'outline'}
          aria-pressed={d === value}
          onClick={() => onChange(d)}
        >
          {d} days
        </Button>
      ))}
    </div>
  )
}
