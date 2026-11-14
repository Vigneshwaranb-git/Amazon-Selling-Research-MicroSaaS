import axios from 'axios'
import api from '@/services/api'
import type {
  AnalyzeResult,
  PainPoint,
  Review,
  ReviewFilterState,
  ReviewPage,
  ReviewSummary,
  SentimentLabel,
} from '@/types/reviews'
import { REVIEW_PAGE_SIZE } from '@/types/reviews'

export interface ApiReview {
  review_id: string
  rating: number | string
  review_text: string | null
  sentiment_score: number | string | null
  sentiment_label: SentimentLabel
  pain_points: string[] | null
  reviewed_at: string | null
}

interface ApiReviewPage {
  items: ApiReview[]
  total: number
  page: number
  page_size: number
}

interface ApiPainPoints {
  asin: string
  items: PainPoint[]
}

export interface ApiSummary {
  asin: string
  pros?: string[] | null
  cons?: string[] | null
  opportunities?: string[] | null
  generated_at: string | null
}

interface ApiAnalyze {
  analyzed: number
  summary: ApiSummary
}

function toNumber(value: number | string | null): number | null {
  if (value === null) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

export function toReview(raw: ApiReview): Review {
  return {
    review_id: raw.review_id,
    rating: toNumber(raw.rating) ?? 0,
    review_text: raw.review_text ?? '',
    sentiment_score: toNumber(raw.sentiment_score),
    sentiment_label: raw.sentiment_label,
    pain_points: raw.pain_points ?? [],
    reviewed_at: raw.reviewed_at,
  }
}

export function toSummary(raw: ApiSummary): ReviewSummary {
  return {
    asin: raw.asin,
    pros: raw.pros ?? [],
    cons: raw.cons ?? [],
    opportunities: raw.opportunities ?? [],
    generated_at: raw.generated_at,
  }
}

export function buildReviewParams(filters: ReviewFilterState): Record<string, string | number> {
  const params: Record<string, string | number> = {
    page: filters.page,
    page_size: REVIEW_PAGE_SIZE,
  }
  if (filters.rating >= 1 && filters.rating <= 5) params.rating = filters.rating
  const keyword = filters.keyword.trim()
  if (keyword) params.keyword = keyword
  return params
}

const base = (asin: string): string => `/reviews/${encodeURIComponent(asin)}`

export async function fetchReviews(asin: string, filters: ReviewFilterState): Promise<ReviewPage> {
  const { data } = await api.get<ApiReviewPage>(base(asin), { params: buildReviewParams(filters) })
  return {
    items: data.items.map(toReview),
    total: data.total,
    page: data.page,
    page_size: data.page_size,
  }
}

/** Resolves to null when no summary has been generated yet (404). */
export async function fetchReviewSummary(asin: string): Promise<ReviewSummary | null> {
  try {
    const { data } = await api.get<ApiSummary>(`${base(asin)}/summary`)
    return toSummary(data)
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) return null
    throw error
  }
}

export async function analyzeReviews(asin: string): Promise<AnalyzeResult> {
  const { data } = await api.post<ApiAnalyze>(`${base(asin)}/analyze`)
  return { analyzed: data.analyzed, summary: toSummary(data.summary) }
}

export async function fetchPainPoints(asin: string): Promise<PainPoint[]> {
  const { data } = await api.get<ApiPainPoints>(`${base(asin)}/pain-points`)
  return data.items.map((p) => ({ ...p, share_pct: Number(p.share_pct), example: p.example ?? null }))
}
