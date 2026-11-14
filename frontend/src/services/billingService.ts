import api from '@/services/api'
import type { SubscriptionStatus, SubscriptionTier } from '@/types'

export type PaidPlan = Exclude<SubscriptionTier, 'free'>

export interface SubscriptionInfo {
  plan: SubscriptionTier
  status: SubscriptionStatus
  current_period_end: string | null
}

export interface CheckoutSession {
  checkout_url: string
}

export async function createCheckout(plan: PaidPlan): Promise<CheckoutSession> {
  const { data } = await api.post<CheckoutSession>('/billing/checkout', { plan })
  return data
}

export async function getSubscription(): Promise<SubscriptionInfo> {
  const { data } = await api.get<SubscriptionInfo>('/billing/subscription')
  return data
}
