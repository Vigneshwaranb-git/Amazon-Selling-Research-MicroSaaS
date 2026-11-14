import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { PainPointChart } from '@/components/reviews/PainPointChart'
import { ReviewFilters } from '@/components/reviews/ReviewFilters'
import { ReviewList } from '@/components/reviews/ReviewList'
import { SentimentSummary } from '@/components/reviews/SentimentSummary'
import {
  useAnalyzeReviews,
  useDebouncedValue,
  usePainPoints,
  useReviews,
  useReviewSummary,
} from '@/hooks/useReviews'
import { DEFAULT_REVIEW_FILTERS, type ReviewFilterState } from '@/types/reviews'

const KEYWORD_DEBOUNCE_MS = 400

export default function ReviewsPage() {
  const { asin = '' } = useParams<{ asin: string }>()
  const [rating, setRating] = useState(DEFAULT_REVIEW_FILTERS.rating)
  const [keywordInput, setKeywordInput] = useState(DEFAULT_REVIEW_FILTERS.keyword)
  const [page, setPage] = useState(DEFAULT_REVIEW_FILTERS.page)
  const keyword = useDebouncedValue(keywordInput, KEYWORD_DEBOUNCE_MS)

  useEffect(() => setPage(1), [keyword])

  const filters: ReviewFilterState = { rating, keyword, page }
  const reviews = useReviews(asin, filters)
  const summary = useReviewSummary(asin)
  const painPoints = usePainPoints(asin)
  const { reload: reloadPainPoints } = painPoints
  const { reload: reloadReviews } = reviews
  const { analyze, analyzing, error: analyzeError } = useAnalyzeReviews(asin, summary.setSummary)

  const handleAnalyze = async (): Promise<void> => {
    const ok = await analyze()
    if (ok) {
      reloadPainPoints()
      reloadReviews()
    }
  }

  return (
    <PageWrapper>
      <main className="mx-auto max-w-5xl space-y-6 p-8">
        <Link to={`/products/${encodeURIComponent(asin)}`} className="text-sm text-muted-foreground hover:underline">
          Back to product
        </Link>
        <header>
          <h1 className="text-2xl font-bold">Review insights</h1>
          <p className="text-sm text-muted-foreground">{asin}</p>
        </header>
        <SentimentSummary
          summary={summary.data}
          loading={summary.loading}
          loadError={summary.error}
          analyzing={analyzing}
          analyzeError={analyzeError}
          onAnalyze={() => void handleAnalyze()}
          onRetry={summary.reload}
        />
        {painPoints.error ? (
          <p role="alert" className="text-destructive">
            {painPoints.error}
          </p>
        ) : (
          <PainPointChart items={painPoints.data ?? []} />
        )}
        <ReviewFilters
          rating={rating}
          keyword={keywordInput}
          onRatingChange={(r) => {
            setRating(r)
            setPage(1)
          }}
          onKeywordChange={setKeywordInput}
          onReset={() => {
            setRating(DEFAULT_REVIEW_FILTERS.rating)
            setKeywordInput('')
            setPage(1)
          }}
        />
        <ReviewList
          data={reviews.data}
          loading={reviews.loading}
          error={reviews.error}
          onRetry={reviews.reload}
          onPageChange={setPage}
        />
      </main>
    </PageWrapper>
  )
}
