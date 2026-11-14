import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '@/services/api'
import {
  exportProductsCsv,
  fetchProduct,
  fetchProductHistory,
  fetchProducts,
  toProduct,
  type ApiProduct,
} from '@/services/productService'
import { DEFAULT_FILTERS } from '@/types/products'

vi.mock('@/services/api', () => ({ default: { get: vi.fn() } }))
const get = vi.mocked(api.get)

const raw: ApiProduct = {
  asin: 'B012345678',
  title: 'Widget',
  category: 'Home',
  image_url: 'http://i/x.jpg',
  bsr: 1200,
  estimated_monthly_sales: 300,
  price: '19.99',
  rating: '4.5',
  review_count: 88,
  saturation_score: 42,
  trend_score: 75,
  estimated_margin_pct: 31.5,
  updated_at: '2025-01-01T00:00:00Z',
}

beforeEach(() => {
  get.mockReset()
})

describe('toProduct', () => {
  it('maps API field names to the UI model and parses decimal strings', () => {
    const p = toProduct(raw)
    expect(p).toMatchObject({
      asin: 'B012345678',
      current_bsr: 1200,
      price: 19.99,
      rating: 4.5,
      estimated_margin: 31.5,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
      brand: null,
    })
  })
  it('derives trend from score with boundaries 60 / 40', () => {
    const trend = (s: number | null) => toProduct({ ...raw, trend_score: s }).trend
    expect(trend(null)).toBeNull()
    expect(trend(60)).toBe('rising')
    expect(trend(100)).toBe('rising')
    expect(trend(59.9)).toBe('stable')
    expect(trend(41)).toBe('stable')
    expect(trend(40)).toBe('declining')
    expect(trend(0)).toBe('declining')
  })
  it('handles nulls, numeric inputs and non-numeric strings', () => {
    const p = toProduct({ ...raw, price: null, rating: 'abc', updated_at: null })
    expect(p.price).toBeNull()
    expect(p.rating).toBeNull()
    expect(p.created_at).toBe('')
    expect(toProduct({ ...raw, price: 12 }).price).toBe(12)
    expect(toProduct({ ...raw, price: '0' }).price).toBe(0)
  })
})

describe('fetchProducts', () => {
  it('maps the page and sends only populated filters', async () => {
    get.mockResolvedValue({ data: { items: [raw], total: 1, page: 2, page_size: 20 } })
    const res = await fetchProducts({
      ...DEFAULT_FILTERS,
      page: 2,
      category: 'Home',
      min_margin: '15',
      max_saturation: '60',
      trend: 'rising',
    })
    expect(get).toHaveBeenCalledWith('/products', {
      params: { page: 2, category: 'Home', min_margin: 15, max_saturation: 60, min_trend: 60 },
    })
    expect(res.total).toBe(1)
    expect(res.page).toBe(2)
    expect(res.page_size).toBe(20)
    expect(res.items[0].asin).toBe('B012345678')
    expect(res.items[0].trend).toBe('rising')
  })
  it('omits empty filters and sends no trend filter for declining', async () => {
    get.mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 20 } })
    await fetchProducts({ ...DEFAULT_FILTERS, trend: 'declining' })
    expect(get).toHaveBeenCalledWith('/products', { params: { page: 1 } })
  })
  it('sends zero-valued numeric filters', async () => {
    get.mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 20 } })
    await fetchProducts({ ...DEFAULT_FILTERS, min_margin: '0', max_saturation: '0' })
    expect(get).toHaveBeenCalledWith('/products', {
      params: { page: 1, min_margin: 0, max_saturation: 0 },
    })
  })
  it('propagates errors', async () => {
    get.mockImplementation(async () => { throw new Error('boom') })
    await expect(fetchProducts(DEFAULT_FILTERS)).rejects.toThrow('boom')
  })
})

describe('fetchProduct', () => {
  it('url-encodes the asin and adapts the payload', async () => {
    get.mockResolvedValue({ data: raw })
    const p = await fetchProduct('B01/2 3')
    expect(get).toHaveBeenCalledWith('/products/B01%2F2%203')
    expect(p.title).toBe('Widget')
  })
})

describe('fetchProductHistory', () => {
  it('unwraps {asin, snapshots} into BsrSnapshot[]', async () => {
    get.mockResolvedValue({
      data: {
        asin: 'B012345678',
        snapshots: [
          { bsr: 1000, price: '9.50', estimated_sales: 10, captured_at: '2025-01-01' },
          { bsr: null, price: null, estimated_sales: null, captured_at: '2025-01-02' },
        ],
      },
    })
    const h = await fetchProductHistory('B012345678')
    expect(get).toHaveBeenCalledWith('/products/B012345678/history')
    expect(Array.isArray(h)).toBe(true)
    expect(h).toHaveLength(2)
    expect(h[0]).toEqual({
      id: 0,
      product_id: 0,
      bsr: 1000,
      price: 9.5,
      estimated_sales: 10,
      captured_at: '2025-01-01',
    })
    expect(h[1]).toMatchObject({ id: 1, bsr: null, price: null, estimated_sales: null })
  })
  it('returns an empty array when there are no snapshots', async () => {
    get.mockResolvedValue({ data: { asin: 'B012345678', snapshots: [] } })
    expect(await fetchProductHistory('B012345678')).toEqual([])
  })
})

describe('exportProductsCsv', () => {
  it('requests a blob with the same filter params', async () => {
    const blob = new Blob(['a,b'])
    get.mockResolvedValue({ data: blob })
    const out = await exportProductsCsv({ ...DEFAULT_FILTERS, category: 'Pets' })
    expect(get).toHaveBeenCalledWith('/products/export', {
      params: { page: 1, category: 'Pets' },
      responseType: 'blob',
    })
    expect(out).toBe(blob)
  })
})
