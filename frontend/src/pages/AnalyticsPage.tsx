import { PageWrapper } from '@/components/layout/PageWrapper'
import { BsrTrendChart } from '@/components/analytics/BsrTrendChart'
import { RangeSelect } from '@/components/analytics/RangeSelect'
import { TopMovers } from '@/components/analytics/TopMovers'
import { TotalsCards } from '@/components/analytics/TotalsCards'
import { TrendDistributionChart } from '@/components/analytics/TrendDistributionChart'
import { useAnalytics } from '@/hooks/useAnalytics'

export default function AnalyticsPage() {
  const { data, loading, error, days, setDays } = useAnalytics(30)
  const isEmpty = data !== null && data.totals.tracked_products === 0 && data.totals.scenarios === 0

  return (
    <PageWrapper>
      <main className="mx-auto max-w-5xl space-y-6 p-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-2xl font-bold">Analytics</h1>
          <RangeSelect value={days} onChange={setDays} />
        </div>
        {loading && <p role="status">Loading analytics...</p>}
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
        {data && (
          <>
            <TotalsCards data={data} />
            {isEmpty && (
              <p className="rounded-xl border p-4 text-sm text-muted-foreground">
                Nothing to analyze yet. Add products to a tracking list or save a calculator scenario to see insights.
              </p>
            )}
            <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
              <BsrTrendChart series={data.bsr_series} />
              <TrendDistributionChart distribution={data.trend_distribution} />
            </div>
            <TopMovers movers={data.top_movers} />
          </>
        )}
      </main>
    </PageWrapper>
  )
}
