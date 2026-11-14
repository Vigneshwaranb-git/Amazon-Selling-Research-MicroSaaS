import axios from 'axios'
import { useCallback, useEffect, useState } from 'react'
import { getErrorMessage } from '@/lib/errors'
import { fetchAdminStats, fetchAdminUsers, updateAdminUser } from '@/services/adminService'
import type { AdminStats, AdminUserPage, AdminUserUpdate } from '@/types/admin'

export const ADMIN_PAGE_SIZE = 20
const SEARCH_DEBOUNCE_MS = 300
export const FORBIDDEN_MESSAGE = 'You do not have permission to view this.'

function describe(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && err.response?.status === 403) return FORBIDDEN_MESSAGE
  return getErrorMessage(err, fallback)
}

export interface UseAdminStats {
  stats: AdminStats | null
  loading: boolean
  error: string | null
  reload: () => void
}

export function useAdminStats(): UseAdminStats {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchAdminStats()
      .then((s) => {
        if (!cancelled) setStats(s)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(describe(err, 'Could not load admin stats.'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { stats, loading, error, reload }
}

export interface UseAdminUsers {
  data: AdminUserPage | null
  loading: boolean
  error: string | null
  search: string
  setSearch: (value: string) => void
  page: number
  setPage: (page: number) => void
  update: (id: number, change: AdminUserUpdate) => Promise<void>
  reload: () => void
}

/** Debounced search and server pagination. Mutations refetch (no optimistic updates). */
export function useAdminUsers(): UseAdminUsers {
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<AdminUserPage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const id = setTimeout(() => {
      if (search !== debounced) {
        setDebounced(search)
        setPage(1)
      }
    }, SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(id)
  }, [search, debounced])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchAdminUsers({ search: debounced, page, page_size: ADMIN_PAGE_SIZE })
      .then((result) => {
        if (cancelled) return
        setData(result)
        setError(null)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(describe(err, 'Could not load users.'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [debounced, page, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])

  const update = useCallback(async (id: number, change: AdminUserUpdate) => {
    try {
      await updateAdminUser(id, change)
    } catch (err: unknown) {
      setError(describe(err, 'Could not update the user.'))
      throw err
    }
    setError(null)
    setTick((t) => t + 1)
  }, [])

  return { data, loading, error, search, setSearch, page, setPage, update, reload }
}
