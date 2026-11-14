export type SubscriptionTier = 'free' | 'pro' | 'business'
export type SubscriptionStatus = 'active' | 'trialing' | 'past_due' | 'canceled' | 'inactive'
export type Sentiment = 'positive' | 'neutral' | 'negative'

export interface User {
  id: number
  email: string
  full_name: string | null
  is_active: boolean
  is_admin: boolean
  created_at: string
}

export interface AccessToken {
  access_token: string
  token_type: string
}

export interface Product {
  id: number
  asin: string
  title: string
  brand: string | null
  category: string | null
  image_url: string | null
  price: number | null
  rating: number | null
  review_count: number | null
  current_bsr: number | null
  estimated_monthly_sales: number | null
  created_at: string
  updated_at: string
}

export interface BsrSnapshot {
  id: number
  product_id: number
  bsr: number | null
  price: number | null
  estimated_sales: number | null
  captured_at: string
}

export interface TrackingListSummary {
  id: number
  name: string
  created_at: string
  product_count: number
}

export interface TrackingList {
  id: number
  user_id: number
  name: string
  description: string | null
  products: Product[]
  created_at: string
}

export interface CostModel {
  id: number
  user_id: number
  name: string
  asin: string | null
  selling_price: number
  product_cost: number
  shipping_cost: number
  referral_fee_pct: number
  fba_fee: number
  storage_fee: number
  ad_cost: number
  other_costs: number
  net_profit: number
  margin_pct: number
  roi_pct: number
  created_at: string
}

export interface ReviewLog {
  id: number
  product_id: number
  review_id: string
  rating: number
  title: string | null
  body: string
  sentiment: Sentiment
  pain_points: string[]
  reviewed_at: string
}

export interface Subscription {
  id: number
  user_id: number
  tier: SubscriptionTier
  status: SubscriptionStatus
  current_period_end: string | null
  cancel_at_period_end: boolean
}
