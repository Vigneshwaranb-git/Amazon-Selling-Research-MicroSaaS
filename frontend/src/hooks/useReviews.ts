import { useCallback, useEffect, useState } from 'react'
import axios from 'axios'
import { getErrorMessage } from '@/lib/errors'
import { useAsync, type AsyncState } from '@/hooks/useAsync'
import {
  analyzeReviews,
  fetchPainPoints,
  fetchReviews,
  fetchReviewSummary,
} from '@/services/reviewService'
import type { PainPoint, ReviewFilterState, ReviewPage, ReviewSummary } from '@/types/reviews'

export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(id)
  }, [value, delayMs])
  return debounced
}

export function useReviews(asin: string, filters: ReviewFilterState): AsyncState<ReviewPage> {
  return useAsync(() => fetchReviews(asin, filters), 'Could not load reviews. Please try again.', [
    asin,
    filters.rating,
    filters.keyword,
    filters.page,
  ])
}

/** `data` is null both while loading and when no summary exists yet (a 404 is not an error). */
export function useReviewSummary(asin: string): AsyncState<ReviewSummary> & {
  setSummary: (summary: ReviewSummary) => void
} {
  const state = useAsync(() => fetchReviewSummary(asin), 'Could not load the AI summary. Please try again.', [asin])
  const [override, setOverride] = useState<ReviewSummary | null>(null)
  useEffect(() => setOverride(null), [asin])
  const setSummary = useCallback((summary: ReviewSummary) => setOverride(summary), [])
  return { ...state, data: override ?? state.data, setSummary }
}

export function usePainPoints(asin: string): AsyncState<PainPoint[]> {
  return useAsync(() => fetchPainPoints(asin), 'Could not load pain points. Please try again.', [asin])
}

export const RATE_LIMIT_MESSAGE = 'You have analyzed reviews too often. Please wait a few minutes and try again.'

export function analyzeErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error) && error.response?.status === 429) return RATE_LIMIT_MESSAGE
  return getErrorMessage(error, 'Could not analyze reviews. Please try again.')
}

export interface UseAnalyze {
  analyze: () => Promise<boolean>
  analyzing: boolean
  error: string | null
}

/** Runs sentiment analysis; calls `onDone` with the fresh summary on success. */
export function useAnalyzeReviews(asin: string, onDone: (summary: ReviewSummary) => void): UseAnalyze {
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const analyze = useCallback(async (): Promise<boolean> => {
    setAnalyzing(true)
    setError(null)
    try {
      const result = await analyzeReviews(asin)
      onDone(result.summary)
      return true
    } catch (err: unknown) {
      setError(analyzeErrorMessage(err))
      return false
    } finally {
      setAnalyzing(false)
    }
  }, [asin, onDone])

  return { analyze, analyzing, error }
}
