import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AxiosError } from 'axios'
import ReviewsPage from '@/pages/ReviewsPage'
import { ReviewFilters } from '@/components/reviews/ReviewFilters'
import { RATE_LIMIT_MESSAGE } from '@/hooks/useReviews'
import * as service from '@/services/reviewService'
import type { ReviewPage, ReviewSummary } from '@/types/reviews'

vi.mock('@/services/reviewService')
const mocked = vi.mocked(service)

const summary: ReviewSummary = {
  asin: 'B0',
  pros: ['Sturdy build'],
  cons: ['Battery dies'],
  opportunities: ['Bigger battery'],
  generated_at: '2025-01-01T00:00:00Z',
}

const page: ReviewPage = {
  items: [
    {
      review_id: 'R1',
      rating: 1,
      review_text: '<script>alert(1)</script> bad',
      sentiment_score: -0.8,
      sentiment_label: 'negative',
      pain_points: ['battery'],
      reviewed_at: '2025-01-01T00:00:00Z',
    },
  ],
  total: 25,
  page: 1,
  page_size: 10,
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/reviews/B0']}>
      <Routes>
        <Route path="/reviews/:asin" element={<ReviewsPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.resetAllMocks()
  mocked.fetchReviews.mockResolvedValue(page)
  mocked.fetchPainPoints.mockResolvedValue([])
  mocked.fetchReviewSummary.mockResolvedValue(null)
})

describe('ReviewsPage', () => {
  it('shows the empty state (not an error) when no summary exists', async () => {
    renderPage()
    expect(await screen.findByTestId('summary-empty')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Analyze reviews' })).toBeEnabled()
    expect(screen.queryByText(/could not load the ai summary/i)).not.toBeInTheDocument()
  })

  it('analyze flow renders the summary and switches to Re-analyze', async () => {
    mocked.analyzeReviews.mockResolvedValue({ analyzed: 5, summary })
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Analyze reviews' }))
    expect(await screen.findByText('Sturdy build')).toBeInTheDocument()
    expect(screen.getByText('Battery dies')).toBeInTheDocument()
    expect(screen.getByText('Bigger battery')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Re-analyze' })).toBeInTheDocument()
  })

  it('shows a friendly message when analyze is rate limited', async () => {
    mocked.analyzeReviews.mockRejectedValue(
      new AxiosError('x', 'ERR', undefined, undefined, {
        status: 429,
        data: {},
        statusText: '',
        headers: {},
        config: { headers: {} } as never,
      }),
    )
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Analyze reviews' }))
    expect(await screen.findByText(RATE_LIMIT_MESSAGE)).toBeInTheDocument()
  })

  it('renders review text as plain text with a sentiment badge', async () => {
    renderPage()
    expect(await screen.findByText('<script>alert(1)</script> bad')).toBeInTheDocument()
    expect(screen.getByTestId('sentiment-badge')).toHaveTextContent('negative')
  })

  it('applies the rating filter and paginates', async () => {
    renderPage()
    await screen.findByText(/bad/)
    await userEvent.selectOptions(screen.getByLabelText('Star rating'), '1')
    await waitFor(() =>
      expect(mocked.fetchReviews).toHaveBeenLastCalledWith('B0', { rating: 1, keyword: '', page: 1 }),
    )
    await userEvent.click(await screen.findByRole('button', { name: 'Next' }))
    await waitFor(() =>
      expect(mocked.fetchReviews).toHaveBeenLastCalledWith('B0', { rating: 1, keyword: '', page: 2 }),
    )
  })

  it('debounces the keyword filter', async () => {
    renderPage()
    await screen.findByText(/bad/)
    const callsBefore = mocked.fetchReviews.mock.calls.length
    await userEvent.type(screen.getByLabelText('Keyword'), 'leak')
    expect(mocked.fetchReviews.mock.calls.length).toBe(callsBefore)
    await waitFor(() =>
      expect(mocked.fetchReviews).toHaveBeenLastCalledWith('B0', { rating: 0, keyword: 'leak', page: 1 }),
    )
    expect(mocked.fetchReviews.mock.calls.length).toBe(callsBefore + 1)
  })
})

describe('ReviewFilters', () => {
  it('emits rating changes and reset', async () => {
    const onRatingChange = vi.fn()
    const onReset = vi.fn()
    render(
      <ReviewFilters rating={0} keyword="" onRatingChange={onRatingChange} onKeywordChange={vi.fn()} onReset={onReset} />,
    )
    await userEvent.selectOptions(screen.getByLabelText('Star rating'), '3')
    expect(onRatingChange).toHaveBeenCalledWith(3)
    await userEvent.click(screen.getByRole('button', { name: 'Reset' }))
    expect(onReset).toHaveBeenCalled()
  })
})
