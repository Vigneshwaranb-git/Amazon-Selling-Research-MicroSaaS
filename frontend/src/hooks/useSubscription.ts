import { useCallback, useEffect, useState } from 'react'
import { getSubscription, type SubscriptionInfo } from '@/services/billingService'

interface UseSubscriptionResult {
  subscription: SubscriptionInfo | null
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

/** Subscription state is always read from the API, never set client-side. */
export function useSubscription(): UseSubscriptionResult {
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      setSubscription(await getSubscription())
    } catch {
      setError('Could not load your subscription.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refetch()
  }, [refetch])

  // Refetch when returning from the hosted checkout (tab regains focus / bfcache restore).
  useEffect(() => {
    const onVisible = (): void => {
      if (document.visibilityState === 'visible') void refetch()
    }
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('pageshow', onVisible)
    return () => {
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('pageshow', onVisible)
    }
  }, [refetch])

  return { subscription, loading, error, refetch }
}
