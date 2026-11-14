export type SentimentLabel = 'positive' | 'neutral' | 'negative'

export interface Review {
  review_id: string
  rating: number
  review_text: string
  sentiment_score: number | null
  sentiment_label: SentimentLabel
  pain_points: string[]
  reviewed_at: string | null
}

export interface ReviewPage {
  items: Review[]
  total: number
  page: number
  page_size: number
}

export interface ReviewSummary {
  asin: string
  pros: string[]
  cons: string[]
  opportunities: string[]
  generated_at: string | null
}

export interface AnalyzeResult {
  analyzed: number
  summary: ReviewSummary
}

export interface PainPoint {
  label: string
  count: number
  share_pct: number
  example: string | null
}

export interface ReviewFilterState {
  /** 0 means any rating. */
  rating: number
  keyword: string
  page: number
}

export const DEFAULT_REVIEW_FILTERS: ReviewFilterState = { rating: 0, keyword: '', page: 1 }
export const REVIEW_PAGE_SIZE = 10
