import api from '@/services/api'
import type { AnalyticsOverview } from '@/types/analytics'

export async function fetchAnalyticsOverview(days: number): Promise<AnalyticsOverview> {
  const { data } = await api.get<AnalyticsOverview>('/analytics/overview', { params: { days } })
  return {
    totals: {
      tracking_lists: data.totals?.tracking_lists ?? 0,
      tracked_products: data.totals?.tracked_products ?? 0,
      scenarios: data.totals?.scenarios ?? 0,
    },
    avg_scenario_margin: data.avg_scenario_margin ?? null,
    trend_distribution: {
      rising: data.trend_distribution?.rising ?? 0,
      stable: data.trend_distribution?.stable ?? 0,
      declining: data.trend_distribution?.declining ?? 0,
    },
    bsr_series: data.bsr_series ?? [],
    top_movers: data.top_movers ?? [],
  }
}
