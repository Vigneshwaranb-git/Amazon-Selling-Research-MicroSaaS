import api from '@/services/api'
import type { DataSourceInfo } from '@/types/meta'

export async function fetchDataSource(): Promise<DataSourceInfo> {
  const { data } = await api.get<DataSourceInfo>('/meta/data-source')
  return data
}
