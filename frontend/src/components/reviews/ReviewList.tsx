import { Button } from '@/components/ui/button'
import { SentimentBadge } from '@/components/reviews/SentimentBadge'
import type { ReviewPage } from '@/types/reviews'

interface ReviewListProps {
  data: ReviewPage | null
  loading: boolean
  error: string | null
  onRetry: () => void
  onPageChange: (page: number) => void
}

const STAR_FULL = '★'
const STAR_EMPTY = '☆'

function Stars({ rating }: { rating: number }) {
  const full = Math.max(0, Math.min(5, Math.round(rating)))
  return (
    <span aria-label={`${full} out of 5 stars`} className="text-amber-500">
      {STAR_FULL.repeat(full)}
      {STAR_EMPTY.repeat(5 - full)}
    </span>
  )
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString()
}

export function ReviewList({ data, loading, error, onRetry, onPageChange }: ReviewListProps) {
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  return (
    <section aria-label="Reviews" className="space-y-3">
      {loading && <p role="status">Loading reviews...</p>}
      {error && (
        <div role="alert" className="space-y-2">
          <p className="text-destructive">{error}</p>
          <Button variant="outline" onClick={onRetry}>
            Retry
          </Button>
        </div>
      )}
      {data && data.items.length === 0 && !loading && !error && (
        <p className="text-sm text-muted-foreground">No reviews match these filters.</p>
      )}
      {data && (
        <ul className="space-y-3">
          {data.items.map((r) => (
            <li key={r.review_id} className="space-y-2 rounded-xl border bg-card p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Stars rating={r.rating} />
                <SentimentBadge label={r.sentiment_label} />
                <span className="text-xs text-muted-foreground">{formatDate(r.reviewed_at)}</span>
              </div>
              {/* Untrusted text: rendered as a plain text node only. */}
              <p className="whitespace-pre-wrap break-words text-sm">{r.review_text}</p>
              {r.pain_points.length > 0 && (
                <ul className="flex flex-wrap gap-1" aria-label="Pain points">
                  {r.pain_points.map((p) => (
                    <li key={p} className="rounded bg-muted px-2 py-0.5 text-xs">
                      {p}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
      {data && data.total > data.page_size && (
        <nav aria-label="Review pagination" className="flex items-center gap-3">
          <Button variant="outline" size="sm" disabled={data.page <= 1} onClick={() => onPageChange(data.page - 1)}>
            Previous
          </Button>
          <span className="text-sm">
            Page {data.page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={data.page >= totalPages}
            onClick={() => onPageChange(data.page + 1)}
          >
            Next
          </Button>
        </nav>
      )}
    </section>
  )
}
