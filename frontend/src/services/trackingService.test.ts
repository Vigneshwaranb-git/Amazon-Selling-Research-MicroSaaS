import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '@/services/api'
import {
  addProductToList,
  createTrackingList,
  deleteTrackingList,
  fetchTrackingList,
  fetchTrackingLists,
  removeProductFromList,
  renameTrackingList,
} from '@/services/trackingService'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))
const mocked = vi.mocked(api)

const apiProduct = {
  asin: 'B012345678',
  title: 'Widget',
  category: null,
  image_url: null,
  bsr: 5,
  estimated_monthly_sales: null,
  price: '10.00',
  rating: null,
  review_count: null,
  saturation_score: null,
  trend_score: 20,
  estimated_margin_pct: null,
  updated_at: null,
}

beforeEach(() => {
  mocked.get.mockReset()
  mocked.post.mockReset()
  mocked.put.mockReset()
  mocked.delete.mockReset()
})

describe('fetchTrackingLists', () => {
  it('returns summaries from a single request (no per-list detail calls)', async () => {
    mocked.get.mockResolvedValue({
      data: [
        { id: 1, name: 'A', created_at: 'c1', product_count: 3 },
        { id: 2, name: 'B', created_at: 'c2', product_count: 0 },
      ],
    })
    const lists = await fetchTrackingLists()
    expect(mocked.get).toHaveBeenCalledTimes(1)
    expect(mocked.get).toHaveBeenCalledWith('/tracking-lists')
    expect(lists).toEqual([
      { id: 1, name: 'A', created_at: 'c1', product_count: 3 },
      { id: 2, name: 'B', created_at: 'c2', product_count: 0 },
    ])
  })
  it('returns [] when there are no lists', async () => {
    mocked.get.mockResolvedValue({ data: [] })
    expect(await fetchTrackingLists()).toEqual([])
  })
  it('propagates errors', async () => {
    mocked.get.mockRejectedValue(new Error('500'))
    await expect(fetchTrackingLists()).rejects.toThrow('500')
  })
})

describe('fetchTrackingList', () => {
  it('loads one list with adapted products', async () => {
    mocked.get.mockResolvedValue({
      data: { id: 1, name: 'A', created_at: 'c1', products: [apiProduct] },
    })
    const list = await fetchTrackingList(1)
    expect(mocked.get).toHaveBeenCalledWith('/tracking-lists/1')
    expect(list).toMatchObject({ id: 1, name: 'A', created_at: 'c1', description: null })
    expect(list.products[0]).toMatchObject({
      asin: 'B012345678',
      current_bsr: 5,
      price: 10,
      trend: 'declining',
    })
  })
})

describe('mutations', () => {
  it('call the expected endpoints', async () => {
    await createTrackingList('N')
    expect(mocked.post).toHaveBeenCalledWith('/tracking-lists', { name: 'N' })
    await renameTrackingList(3, 'R')
    expect(mocked.put).toHaveBeenCalledWith('/tracking-lists/3', { name: 'R' })
    await deleteTrackingList(3)
    expect(mocked.delete).toHaveBeenCalledWith('/tracking-lists/3')
    await addProductToList(3, 'B012345678')
    expect(mocked.post).toHaveBeenCalledWith('/tracking-lists/3/products', { asin: 'B012345678' })
    await removeProductFromList(3, 'B0 1')
    expect(mocked.delete).toHaveBeenCalledWith('/tracking-lists/3/products/B0%201')
  })
})
