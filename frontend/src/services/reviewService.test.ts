import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError } from 'axios'
import api from '@/services/api'
import {
  analyzeReviews,
  buildReviewParams,
  fetchPainPoints,
  fetchReviews,
  fetchReviewSummary,
  toReview,
  type ApiReview,
} from '@/services/reviewService'
import { DEFAULT_REVIEW_FILTERS } from '@/types/reviews'

vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
const get = vi.mocked(api.get)
const post = vi.mocked(api.post)

const raw: ApiReview = {
  review_id: 'R1',
  rating: '4',
  review_text: null,
  sentiment_score: '0.55',
  sentiment_label: 'positive',
  pain_points: null,
  reviewed_at: '2025-01-01T00:00:00Z',
}

function httpError(status: number): AxiosError {
  return new AxiosError('fail', 'ERR', undefined, undefined, {
    status,
    data: {},
    statusText: '',
    headers: {},
    config: { headers: {} } as never,
  })
}

beforeEach(() => {
  get.mockReset()
  post.mockReset()
})

describe('toReview', () => {
  it('parses numeric strings and nulls', () => {
    expect(toReview(raw)).toMatchObject({
      rating: 4,
      sentiment_score: 0.55,
      review_text: '',
      pain_points: [],
    })
  })
})

describe('buildReviewParams', () => {
  it('omits empty filters and trims the keyword', () => {
    expect(buildReviewParams(DEFAULT_REVIEW_FILTERS)).toEqual({ page: 1, page_size: 10 })
    expect(buildReviewParams({ rating: 2, keyword: '  leak ', page: 3 })).toEqual({
      page: 3,
      page_size: 10,
      rating: 2,
      keyword: 'leak',
    })
  })
})

describe('review service calls', () => {
  it('fetchReviews maps the page and sends params', async () => {
    get.mockResolvedValue({ data: { items: [raw], total: 1, page: 1, page_size: 10 } })
    const page = await fetchReviews('B0', { rating: 5, keyword: '', page: 1 })
    expect(get).toHaveBeenCalledWith('/reviews/B0', { params: { page: 1, page_size: 10, rating: 5 } })
    expect(page.items[0].rating).toBe(4)
  })

  it('fetchReviewSummary returns null on 404', async () => {
    get.mockRejectedValue(httpError(404))
    await expect(fetchReviewSummary('B0')).resolves.toBeNull()
  })

  it('fetchReviewSummary rethrows other errors', async () => {
    get.mockRejectedValue(httpError(500))
    await expect(fetchReviewSummary('B0')).rejects.toBeTruthy()
  })

  it('analyzeReviews posts and maps the summary', async () => {
    post.mockResolvedValue({
      data: { analyzed: 12, summary: { asin: 'B0', pros: ['a'], cons: [], opportunities: ['x'], generated_at: 't' } },
    })
    const result = await analyzeReviews('B0')
    expect(post).toHaveBeenCalledWith('/reviews/B0/analyze')
    expect(result.analyzed).toBe(12)
    expect(result.summary.pros).toEqual(['a'])
  })

  it('fetchPainPoints returns items', async () => {
    get.mockResolvedValue({
      data: { asin: 'B0', items: [{ label: 'Leaks', count: 3, share_pct: '25.5', example: null }] },
    })
    const items = await fetchPainPoints('B0')
    expect(items[0].share_pct).toBe(25.5)
  })
})
