import { Link } from 'react-router-dom'
import type { TopMover } from '@/types/analytics'

/** BSR change: a negative percentage means the rank number fell, which is an improvement. */
function describeChange(pct: number): string {
  const rounded = Math.abs(pct).toFixed(1)
  if (pct < 0) return `Improved ${rounded}%`
  if (pct > 0) return `Worsened ${rounded}%`
  return 'No change'
}

export function TopMovers({ movers }: { movers: TopMover[] }) {
  return (
    <section aria-label="Top movers" className="rounded-xl border bg-card p-4">
      <h2 className="mb-2 font-semibold">Top movers</h2>
      {movers.length === 0 ? (
        <p className="text-sm text-muted-foreground">No movers in this range.</p>
      ) : (
        <ul className="divide-y">
          {movers.map((m) => (
            <li key={m.asin} className="flex items-center justify-between gap-4 py-2 text-sm">
              <Link to={`/products/${m.asin}`} className="min-w-0 truncate hover:underline">
                {m.title} <span className="text-muted-foreground">({m.asin})</span>
              </Link>
              <span className="shrink-0 tabular-nums">{describeChange(m.bsr_change_pct)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
