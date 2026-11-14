import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { AdminStats } from '@/types/admin'

interface Stat {
  label: string
  value: number
}

function Tile({ label, value }: Stat) {
  return (
    <Card className="gap-2 py-4">
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-bold tabular-nums">{value.toLocaleString()}</p>
      </CardContent>
    </Card>
  )
}

export function StatsCards({ stats }: { stats: AdminStats }) {
  const tiles: Stat[] = [
    { label: 'Total users', value: stats.total_users },
    { label: 'Active users', value: stats.active_users },
    { label: 'New (7 days)', value: stats.new_users_7d },
    { label: 'New (30 days)', value: stats.new_users_30d },
    { label: 'Admins', value: stats.admins },
    { label: 'Active subscriptions', value: stats.active_subscriptions },
    { label: 'Tracked products', value: stats.tracked_products },
    { label: 'Tracking lists', value: stats.tracking_lists },
    { label: 'Scenarios', value: stats.scenarios },
  ]
  const plans: Stat[] = [
    { label: 'Free', value: stats.subscriptions_by_plan.free },
    { label: 'Pro', value: stats.subscriptions_by_plan.pro },
    { label: 'Business', value: stats.subscriptions_by_plan.business },
  ]
  return (
    <div className="space-y-6">
      <section aria-label="Platform statistics" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {tiles.map((t) => (
          <Tile key={t.label} {...t} />
        ))}
      </section>
      <section aria-label="Subscriptions by plan" className="space-y-2">
        <h2 className="font-semibold">Subscriptions by plan</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          {plans.map((p) => (
            <Tile key={p.label} {...p} />
          ))}
        </div>
      </section>
    </div>
  )
}
