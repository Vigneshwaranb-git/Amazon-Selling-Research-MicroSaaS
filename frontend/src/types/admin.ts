export type PlanTier = 'free' | 'pro' | 'business'

export interface AdminUser {
  id: number
  email: string
  full_name: string | null
  is_active: boolean
  is_admin: boolean
  is_verified: boolean
  oauth_provider: string | null
  created_at: string
  plan: PlanTier
}

export interface AdminUserPage {
  items: AdminUser[]
  total: number
  page: number
  page_size: number
}

export interface AdminUserUpdate {
  is_active?: boolean
  is_admin?: boolean
}

export interface AdminUserQuery {
  search: string
  page: number
  page_size: number
}

export interface AdminStats {
  total_users: number
  active_users: number
  new_users_7d: number
  new_users_30d: number
  admins: number
  subscriptions_by_plan: Record<PlanTier, number>
  active_subscriptions: number
  tracked_products: number
  tracking_lists: number
  scenarios: number
}
