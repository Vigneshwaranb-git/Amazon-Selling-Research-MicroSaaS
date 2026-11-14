export type AnalyticsRange = 7 | 30 | 90

export interface AnalyticsTotals {
  tracking_lists: number
  tracked_products: number
  scenarios: number
}

export interface TrendDistribution {
  rising: number
  stable: number
  declining: number
}

export interface BsrPoint {
  date: string
  avg_bsr: number
}

export interface TopMover {
  asin: string
  title: string
  bsr_change_pct: number
}

export interface AnalyticsOverview {
  totals: AnalyticsTotals
  avg_scenario_margin: number | null
  trend_distribution: TrendDistribution
  bsr_series: BsrPoint[]
  top_movers: TopMover[]
}
