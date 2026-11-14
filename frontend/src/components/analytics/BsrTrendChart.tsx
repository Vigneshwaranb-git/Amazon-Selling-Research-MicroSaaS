import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { BsrPoint } from '@/types/analytics'

export function BsrTrendChart({ series }: { series: BsrPoint[] }) {
  const first = series[0]
  const last = series[series.length - 1]
  const summary = first && last
    ? `Average best sellers rank from ${first.date} (${Math.round(first.avg_bsr)}) to ${last.date} (${Math.round(last.avg_bsr)}). Lower is better.`
    : ''
  return (
    <section aria-label="Average BSR trend" className="rounded-xl border bg-card p-4">
      <h2 className="mb-2 font-semibold">Average BSR trend</h2>
      {series.length === 0 ? (
        <p className="text-sm text-muted-foreground">No BSR data in this range yet. Track products to see trends.</p>
      ) : (
        <>
          <div role="img" aria-label={summary} className="text-muted-foreground">
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={series}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis dataKey="date" stroke="currentColor" tick={{ fill: 'currentColor' }} />
                <YAxis reversed stroke="currentColor" tick={{ fill: 'currentColor' }} width={56} />
                <Tooltip
                  formatter={(value) => [Math.round(Number(value)).toLocaleString(), 'Avg BSR']}
                  contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)' }}
                  labelStyle={{ color: 'var(--card-foreground)' }}
                  itemStyle={{ color: 'var(--card-foreground)' }}
                />
                <Line type="monotone" dataKey="avg_bsr" name="Avg BSR" stroke="var(--primary)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <details className="mt-2 text-sm">
            <summary className="cursor-pointer text-muted-foreground">View as table</summary>
            <table className="mt-2 w-full text-left">
              <caption className="sr-only">Average BSR by date</caption>
              <thead>
                <tr>
                  <th scope="col" className="p-1">Date</th>
                  <th scope="col" className="p-1">Avg BSR</th>
                </tr>
              </thead>
              <tbody>
                {series.map((p) => (
                  <tr key={p.date}>
                    <td className="p-1">{p.date}</td>
                    <td className="p-1 tabular-nums">{Math.round(p.avg_bsr).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </>
      )}
    </section>
  )
}
