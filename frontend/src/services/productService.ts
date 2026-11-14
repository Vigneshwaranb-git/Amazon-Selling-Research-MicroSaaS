import api from '@/services/api'
import type { BsrSnapshot } from '@/types'
import type {
  ProductFilters,
  ProductHistory,
  ProductPage,
  Trend,
  TrackerProduct,
} from '@/types/products'

/** Numeric values the API may send as decimal strings. */
type Numeric = string | number | null

export interface ApiProduct {
  asin: string
  title: string
  category: string | null
  image_url: string | null
  bsr: number | null
  estimated_monthly_sales: number | null
  price: Numeric
  rating: Numeric
  review_count: number | null
  saturation_score: number | null
  trend_score: number | null
  estimated_margin_pct: number | null
  updated_at: string | null
}

interface ApiProductPage {
  items: ApiProduct[]
  total: number
  page: number
  page_size: number
}

interface ApiSnapshot {
  bsr: number | null
  price: Numeric
  estimated_sales: number | null
  captured_at: string
}

interface ApiHistory {
  asin: string
  snapshots: ApiSnapshot[]
}

/** Minimum trend score treated as "rising"; the API only filters on a minimum score. */
const RISING_MIN_SCORE = 60
const DECLINING_MAX_SCORE = 40

function toNumber(value: Numeric | undefined): number | null {
  if (value === null || value === undefined) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function trendFromScore(score: number | null): Trend | null {
  if (score === null) return null
  if (score >= RISING_MIN_SCORE) return 'rising'
  if (score <= DECLINING_MAX_SCORE) return 'declining'
  return 'stable'
}

export function toProduct(raw: ApiProduct): TrackerProduct {
  return {
    id: 0,
    asin: raw.asin,
    title: raw.title,
    brand: null,
    category: raw.category,
    image_url: raw.image_url,
    price: toNumber(raw.price),
    rating: toNumber(raw.rating),
    review_count: raw.review_count,
    current_bsr: raw.bsr,
    estimated_monthly_sales: raw.estimated_monthly_sales,
    created_at: raw.updated_at ?? '',
    updated_at: raw.updated_at ?? '',
    estimated_margin: raw.estimated_margin_pct,
    saturation_score: raw.saturation_score,
    trend_score: raw.trend_score,
    trend: trendFromScore(raw.trend_score),
  }
}

function buildParams(filters: ProductFilters): Record<string, string | number> {
  const params: Record<string, string | number> = { page: filters.page }
  if (filters.category) params.category = filters.category
  if (filters.min_margin !== '') params.min_margin = Number(filters.min_margin)
  if (filters.max_saturation !== '') params.max_saturation = Number(filters.max_saturation)
  if (filters.trend === 'rising') params.min_trend = RISING_MIN_SCORE
  return params
}

export async function fetchProducts(filters: ProductFilters): Promise<ProductPage> {
  const { data } = await api.get<ApiProductPage>('/products', { params: buildParams(filters) })
  return {
    items: data.items.map(toProduct),
    total: data.total,
    page: data.page,
    page_size: data.page_size,
  }
}

export async function fetchProduct(asin: string): Promise<TrackerProduct> {
  const { data } = await api.get<ApiProduct>(`/products/${encodeURIComponent(asin)}`)
  return toProduct(data)
}

export async function fetchProductHistory(asin: string): Promise<ProductHistory> {
  const { data } = await api.get<ApiHistory>(`/products/${encodeURIComponent(asin)}/history`)
  return data.snapshots.map(
    (s, index): BsrSnapshot => ({
      id: index,
      product_id: 0,
      bsr: s.bsr,
      price: toNumber(s.price),
      estimated_sales: s.estimated_sales,
      captured_at: s.captured_at,
    }),
  )
}

export async function exportProductsCsv(filters: ProductFilters): Promise<Blob> {
  const { data } = await api.get<Blob>('/products/export', {
    params: buildParams(filters),
    responseType: 'blob',
  })
  return data
}
