import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { AnalyticsOverview } from '@/types/analytics'

export function TotalsCards({ data }: { data: AnalyticsOverview }) {
  const margin = data.avg_scenario_margin === null ? 'N/A' : `${data.avg_scenario_margin.toFixed(1)}%`
  const tiles: { label: string; value: string }[] = [
    { label: 'Tracking lists', value: data.totals.tracking_lists.toLocaleString() },
    { label: 'Tracked products', value: data.totals.tracked_products.toLocaleString() },
    { label: 'Scenarios', value: data.totals.scenarios.toLocaleString() },
    { label: 'Avg scenario margin', value: margin },
  ]
  return (
    <section aria-label="Totals" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {tiles.map((t) => (
        <Card key={t.label} className="gap-2 py-4">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">{t.label}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold tabular-nums">{t.value}</p>
          </CardContent>
        </Card>
      ))}
    </section>
  )
}
