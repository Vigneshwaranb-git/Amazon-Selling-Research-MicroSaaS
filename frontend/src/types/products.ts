import type { BsrSnapshot, Product } from '@/types'

export type Trend = 'rising' | 'stable' | 'declining'

export interface TrackerProduct extends Product {
  estimated_margin?: number | null
  saturation_score?: number | null
  trend_score?: number | null
  trend?: Trend | null
}

export interface ProductFilters {
  category: string
  min_margin: string
  max_saturation: string
  trend: Trend | ''
  page: number
}

export interface ProductPage {
  items: TrackerProduct[]
  total: number
  page: number
  page_size: number
}

export type ProductHistory = BsrSnapshot[]

export const DEFAULT_FILTERS: ProductFilters = {
  category: '',
  min_margin: '',
  max_saturation: '',
  trend: '',
  page: 1,
}
