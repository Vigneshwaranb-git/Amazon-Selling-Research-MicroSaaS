import { useEffect, useState } from 'react'
import { fetchDataSource } from '@/services/metaService'
import type { DataSourceInfo } from '@/types/meta'

/** Module-level cache: the data source is fetched once per page load and shared by all consumers. */
let pending: Promise<DataSourceInfo | null> | null = null
let resolved: DataSourceInfo | null = null

function load(): Promise<DataSourceInfo | null> {
  pending ??= fetchDataSource()
    .then((info) => {
      resolved = info
      return info
    })
    // Fail soft: transparency info is optional, so any error simply renders nothing.
    .catch(() => null)
  return pending
}

/** Test helper: forget the cached data source. */
export function resetDataSourceCache(): void {
  pending = null
  resolved = null
}

/** Returns the active data source, or null while loading or if the request failed. */
export function useDataSource(): DataSourceInfo | null {
  const [info, setInfo] = useState<DataSourceInfo | null>(resolved)

  useEffect(() => {
    if (resolved) return
    let cancelled = false
    void load().then((result) => {
      if (!cancelled) setInfo(result)
    })
    return () => {
      cancelled = true
    }
  }, [])

  return info
}
