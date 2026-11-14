import { useEffect, useState } from 'react'
import { getErrorMessage } from '@/lib/errors'
import { fetchAnalyticsOverview } from '@/services/analyticsService'
import type { AnalyticsOverview, AnalyticsRange } from '@/types/analytics'

export interface UseAnalytics {
  data: AnalyticsOverview | null
  loading: boolean
  error: string | null
  days: AnalyticsRange
  setDays: (days: AnalyticsRange) => void
}

export function useAnalytics(initial: AnalyticsRange = 30): UseAnalytics {
  const [days, setDays] = useState<AnalyticsRange>(initial)
  const [data, setData] = useState<AnalyticsOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchAnalyticsOverview(days)
      .then((result) => {
        if (!cancelled) setData(result)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(getErrorMessage(err, 'Could not load analytics. Please try again.'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [days])

  return { data, loading, error, days, setDays }
}
