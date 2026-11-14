import { useCallback, useEffect, useState } from 'react'
import { getErrorMessage } from '@/lib/errors'
import {
  addProductToList,
  createTrackingList,
  deleteTrackingList,
  fetchTrackingList,
  fetchTrackingLists,
  removeProductFromList,
  renameTrackingList,
} from '@/services/trackingService'
import type { TrackingList, TrackingListSummary } from '@/types'

export interface UseTrackingLists {
  lists: TrackingListSummary[]
  loading: boolean
  error: string | null
  reload: () => Promise<void>
  create: (name: string) => Promise<void>
  rename: (id: number, name: string) => Promise<void>
  remove: (id: number) => Promise<void>
  addProduct: (id: number, asin: string) => Promise<void>
  removeProduct: (id: number, asin: string) => Promise<void>
}

/** Summaries only. Mutations refresh just the summary list (one request). */
export function useTrackingLists(): UseTrackingLists {
  const [lists, setLists] = useState<TrackingListSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    try {
      setError(null)
      setLists(await fetchTrackingLists())
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Could not load your lists. Please try again.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  const mutate = useCallback(
    async (action: () => Promise<unknown>) => {
      try {
        await action()
      } catch (err: unknown) {
        setError(getErrorMessage(err, 'That action failed. Please try again.'))
        throw err
      }
      await reload()
    },
    [reload],
  )

  return {
    lists,
    loading,
    error,
    reload,
    create: (name) => mutate(() => createTrackingList(name)),
    rename: (id, name) => mutate(() => renameTrackingList(id, name)),
    remove: (id) => mutate(() => deleteTrackingList(id)),
    addProduct: (id, asin) => mutate(() => addProductToList(id, asin)),
    removeProduct: (id, asin) => mutate(() => removeProductFromList(id, asin)),
  }
}

export interface UseTrackingListDetail {
  list: TrackingList | null
  loading: boolean
  error: string | null
  reload: () => void
}

/** Loads one list (with products) from GET /tracking-lists/{id}; refetches only when `id` changes or `reload` is called. */
export function useTrackingListDetail(id: number | null): UseTrackingListDetail {
  const [list, setList] = useState<TrackingList | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (id === null) {
      setList(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchTrackingList(id)
      .then((result) => {
        if (!cancelled) setList(result)
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setList(null)
          setError(getErrorMessage(err, 'Could not load this list. Please try again.'))
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [id, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { list, loading, error, reload }
}
