import { motion } from 'framer-motion'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { BsrSnapshot } from '@/types'

export function BsrChart({ history }: { history: BsrSnapshot[] }) {
  const data = history.map((h) => ({ date: h.captured_at.slice(0, 10), bsr: h.bsr }))
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
