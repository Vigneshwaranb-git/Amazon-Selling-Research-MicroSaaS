import { cn } from '@/lib/utils'
import type { SentimentLabel } from '@/types/reviews'

const STYLES: Record<SentimentLabel, string> = {
  positive: 'bg-emerald-100 text-emerald-800',
  neutral: 'bg-slate-100 text-slate-700',
  negative: 'bg-red-100 text-red-800',
}

export function SentimentBadge({ label }: { label: SentimentLabel }) {
  return (
    <span
      data-testid="sentiment-badge"
      className={cn('rounded-full px-2 py-0.5 text-xs font-medium capitalize', STYLES[label])}
    >
      {label}
    </span>
  )
}
