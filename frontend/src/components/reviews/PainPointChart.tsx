import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { PainPoint } from '@/types/reviews'

export function PainPointChart({ items }: { items: PainPoint[] }) {
  const data = items.map((p) => ({ label: p.label, count: p.count, share: p.share_pct }))
  return (
    <section aria-label="Pain points" className="rounded-2xl border bg-card p-4">
      <h2 className="mb-2 font-semibold">Recurring complaints</h2>
      {data.length === 0 ? (
        <p className="text-sm text-muted-foreground">No pain points detected yet.</p>
      ) : (
        <ResponsiveContainer width="100%" height={Math.max(160, data.length * 40)}>
          <BarChart data={data} layout="vertical" margin={{ left: 16 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" allowDecimals={false} />
            <YAxis type="category" dataKey="label" width={120} />
            <Tooltip />
            <Bar dataKey="count" name="Mentions" fill="#ef4444" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </section>
  )
}
