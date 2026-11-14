import api from '@/services/api'
import type { AdminStats, AdminUser, AdminUserPage, AdminUserQuery, AdminUserUpdate, PlanTier } from '@/types/admin'

const PLANS: PlanTier[] = ['free', 'pro', 'business']

function toPlan(value: unknown): PlanTier {
  return PLANS.find((p) => p === value) ?? 'free'
}

export function toAdminUser(u: AdminUser): AdminUser {
  return {
    id: u.id,
    email: u.email,
    full_name: u.full_name ?? null,
    is_active: Boolean(u.is_active),
    is_admin: Boolean(u.is_admin),
    is_verified: Boolean(u.is_verified),
    oauth_provider: u.oauth_provider ?? null,
    created_at: u.created_at,
    plan: toPlan(u.plan),
  }
}

export async function fetchAdminUsers(query: AdminUserQuery): Promise<AdminUserPage> {
  const params: Record<string, string | number> = { page: query.page, page_size: query.page_size }
  const search = query.search.trim()
  if (search) params.search = search
  const { data } = await api.get<AdminUserPage>('/admin/users', { params })
  return {
    items: data.items.map(toAdminUser),
    total: data.total,
    page: data.page,
    page_size: data.page_size,
  }
}

export async function updateAdminUser(id: number, update: AdminUserUpdate): Promise<AdminUser> {
  const { data } = await api.put<AdminUser>(`/admin/users/${id}`, update)
  return toAdminUser(data)
}

export async function fetchAdminStats(): Promise<AdminStats> {
  const { data } = await api.get<AdminStats>('/admin/stats')
  const by = data.subscriptions_by_plan
  return {
    ...data,
    subscriptions_by_plan: { free: by?.free ?? 0, pro: by?.pro ?? 0, business: by?.business ?? 0 },
  }
}
