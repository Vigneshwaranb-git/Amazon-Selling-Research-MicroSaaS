import { motion } from 'framer-motion'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { BsrSnapshot } from '@/types'

export function SalesChart({ history }: { history: BsrSnapshot[] }) {
  const data = history.map((h) => ({ date: h.captured_at.slice(0, 10), sales: h.estimated_sales ?? 0 }))
  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="rounded-2xl border bg-card p-4"
      aria-label="Estimated sales"
    >
      <h2 className="mb-2 font-semibold">Estimated Sales</h2>
      {data.length === 0 ? (
        <p className="text-sm text-muted-foreground">No history yet.</p>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Area type="monotone" dataKey="sales" stroke="#ec4899" fill="#ec4899" fillOpacity={0.25} />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </motion.section>
  )
}
