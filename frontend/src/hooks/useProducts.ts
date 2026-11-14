import { useCallback, useEffect, useState } from 'react'
import { getErrorMessage } from '@/lib/errors'
import { fetchProduct, fetchProductHistory, fetchProducts } from '@/services/productService'
import type { ProductFilters, ProductHistory, ProductPage, TrackerProduct } from '@/types/products'

export interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
  reload: () => void
}

function useAsync<T>(load: () => Promise<T>, failureMessage: string, deps: readonly unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    load()
      .then((result) => {
        if (!cancelled) setData(result)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(getErrorMessage(err, failureMessage))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, loading, error, reload }
}

export function useProducts(filters: ProductFilters): AsyncState<ProductPage> {
  return useAsync(() => fetchProducts(filters), 'Could not load products. Please try again.', [
    filters.category,
    filters.min_margin,
    filters.max_saturation,
    filters.trend,
    filters.page,
  ])
}

export function useProduct(asin: string): AsyncState<TrackerProduct> {
  return useAsync(() => fetchProduct(asin), 'Could not load this product. Please try again.', [asin])
}

export function useProductHistory(asin: string): AsyncState<ProductHistory> {
  return useAsync(() => fetchProductHistory(asin), 'Could not load price history. Please try again.', [asin])
}
