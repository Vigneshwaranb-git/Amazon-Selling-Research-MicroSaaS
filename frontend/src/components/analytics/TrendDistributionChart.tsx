import type { TrendDistribution } from '@/types/analytics'

interface Row {
  key: keyof TrendDistribution
  label: string
  bar: string
}

const ROWS: Row[] = [
  { key: 'rising', label: 'Rising', bar: 'bg-primary' },
  { key: 'stable', label: 'Stable', bar: 'bg-muted-foreground' },
  { key: 'declining', label: 'Declining', bar: 'bg-destructive' },
]

const WIDTH_CLASSES = [
  'w-0', 'w-[10%]', 'w-[20%]', 'w-[30%]', 'w-[40%]', 'w-[50%]', 'w-[60%]', 'w-[70%]', 'w-[80%]', 'w-[90%]', 'w-full',
]

export function TrendDistributionChart({ distribution }: { distribution: TrendDistribution }) {
  const total = distribution.rising + distribution.stable + distribution.declining
  const summary = ROWS.map((r) => `${r.label} ${distribution[r.key]}`).join(', ')
  return (
    <section aria-label="Trend distribution" className="rounded-xl border bg-card p-4">
      <h2 className="mb-2 font-semibold">Trend distribution</h2>
      {total === 0 ? (
        <p className="text-sm text-muted-foreground">No tracked products to classify yet.</p>
      ) : (
        <>
          <ul role="img" aria-label={`Trend distribution: ${summary}`} className="space-y-3">
            {ROWS.map((r) => {
              const count = distribution[r.key]
              const pct = Math.round((count / total) * 100)
              const width = WIDTH_CLASSES[Math.round(pct / 10)] ?? 'w-0'
              return (
                <li key={r.key} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span>{r.label}</span>
                    <span className="tabular-nums text-muted-foreground">
                      {count} ({pct}%)
                    </span>
                  </div>
                  <div className="h-3 w-full rounded-full bg-muted">
                    <div className={`h-3 rounded-full ${r.bar} ${width}`} />
                  </div>
                </li>
              )
            })}
          </ul>
          <table className="sr-only">
            <caption>Trend distribution</caption>
            <thead>
              <tr>
                <th scope="col">Trend</th>
                <th scope="col">Products</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map((r) => (
                <tr key={r.key}>
                  <td>{r.label}</td>
                  <td>{distribution[r.key]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  )
}
