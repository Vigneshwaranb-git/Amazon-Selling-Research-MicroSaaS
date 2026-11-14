import api from '@/services/api'
import { toProduct, type ApiProduct } from '@/services/productService'
import type { TrackingList, TrackingListSummary } from '@/types'

interface ApiTrackingListDetail {
  id: number
  name: string
  created_at: string
  products: ApiProduct[]
}

/** Lightweight summaries (with `product_count`); products are loaded per list via `fetchTrackingList`. */
export async function fetchTrackingLists(): Promise<TrackingListSummary[]> {
  const { data } = await api.get<TrackingListSummary[]>('/tracking-lists')
  return data.map((s) => ({
    id: s.id,
    name: s.name,
    created_at: s.created_at,
    product_count: s.product_count,
  }))
}

export async function fetchTrackingList(id: number): Promise<TrackingList> {
  const { data } = await api.get<ApiTrackingListDetail>(`/tracking-lists/${id}`)
  return {
    id: data.id,
    user_id: 0,
    name: data.name,
    description: null,
    products: data.products.map(toProduct),
    created_at: data.created_at,
  }
}

export async function createTrackingList(name: string): Promise<void> {
  await api.post('/tracking-lists', { name })
}

export async function renameTrackingList(id: number, name: string): Promise<void> {
  await api.put(`/tracking-lists/${id}`, { name })
}

export async function deleteTrackingList(id: number): Promise<void> {
  await api.delete(`/tracking-lists/${id}`)
}

export async function addProductToList(id: number, asin: string): Promise<void> {
  await api.post(`/tracking-lists/${id}/products`, { asin })
}

export async function removeProductFromList(id: number, asin: string): Promise<void> {
  await api.delete(`/tracking-lists/${id}/products/${encodeURIComponent(asin)}`)
}
