import { motion } from 'framer-motion'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatSnapshotDate } from '@/lib/dates'
import type { BsrSnapshot } from '@/types'
import type { DataProvider } from '@/types/meta'

interface BsrChartProps {
  history: BsrSnapshot[]
  provider?: DataProvider | null
}

export function BsrChart({ history, provider = null }: BsrChartProps) {
  const data = history.map((h) => ({ date: h.captured_at.slice(0, 10), bsr: h.bsr }))
  const single = data.length === 1 ? data[0] : null
  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border bg-card p-4"
      aria-label="BSR history"
    >
      <h2 className="mb-2 font-semibold">Best Sellers Rank</h2>
      {data.length === 0 ? (
        <p className="text-sm text-muted-foreground">No history yet.</p>
      ) : single ? (
        <div className="space-y-1">
          <p className="text-3xl font-bold">{single.bsr === null ? '-' : `#${single.bsr.toLocaleString('en-US')}`}</p>
          <p className="text-sm text-muted-foreground">Snapshot ({formatSnapshotDate(single.date)})</p>
          <p className="text-sm text-muted-foreground">
            {provider === 'dataset'
              ? 'This dataset provides a single snapshot.'
              : 'Only one data point so far; history builds as snapshots are collected.'}
          </p>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis reversed />
            <Tooltip />
            <Line connectNulls={false} type="monotone" dataKey="bsr" stroke="#8b5cf6" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </motion.section>
  )
}
