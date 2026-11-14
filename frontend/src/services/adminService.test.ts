import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '@/services/api'
import { fetchAdminStats, fetchAdminUsers, updateAdminUser } from '@/services/adminService'
import { fetchAnalyticsOverview } from '@/services/analyticsService'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}))
const mocked = vi.mocked(api)

const apiUser = {
  id: 1,
  email: 'a@b.com',
  full_name: null,
  is_active: true,
  is_admin: false,
  is_verified: true,
  oauth_provider: null,
  created_at: '2026-01-01T00:00:00Z',
  plan: 'pro',
}

beforeEach(() => {
  mocked.get.mockReset()
  mocked.put.mockReset()
})

describe('adminService', () => {
  it('sends search/page params and omits blank search', async () => {
    mocked.get.mockResolvedValue({ data: { items: [apiUser], total: 1, page: 2, page_size: 20 } })
    const result = await fetchAdminUsers({ search: ' bob ', page: 2, page_size: 20 })
    expect(mocked.get).toHaveBeenCalledWith('/admin/users', { params: { page: 2, page_size: 20, search: 'bob' } })
    expect(result.items[0]).toMatchObject({ id: 1, plan: 'pro' })
    await fetchAdminUsers({ search: '  ', page: 1, page_size: 20 })
    expect(mocked.get).toHaveBeenLastCalledWith('/admin/users', { params: { page: 1, page_size: 20 } })
  })

  it('falls back to free for unknown plans', async () => {
    mocked.get.mockResolvedValue({
      data: { items: [{ ...apiUser, plan: 'weird' }], total: 1, page: 1, page_size: 20 },
    })
    const result = await fetchAdminUsers({ search: '', page: 1, page_size: 20 })
    expect(result.items[0]?.plan).toBe('free')
  })

  it('updates a user via PUT', async () => {
    mocked.put.mockResolvedValue({ data: { ...apiUser, is_active: false } })
    const updated = await updateAdminUser(1, { is_active: false })
    expect(mocked.put).toHaveBeenCalledWith('/admin/users/1', { is_active: false })
    expect(updated.is_active).toBe(false)
  })

  it('fills missing plan counts in stats', async () => {
    mocked.get.mockResolvedValue({ data: { total_users: 3, subscriptions_by_plan: { pro: 2 } } })
    const stats = await fetchAdminStats()
    expect(stats.subscriptions_by_plan).toEqual({ free: 0, pro: 2, business: 0 })
  })
})

describe('analyticsService', () => {
  it('passes days and normalizes missing fields', async () => {
    mocked.get.mockResolvedValue({ data: { totals: { tracking_lists: 1 } } })
    const overview = await fetchAnalyticsOverview(90)
    expect(mocked.get).toHaveBeenCalledWith('/analytics/overview', { params: { days: 90 } })
    expect(overview.totals).toEqual({ tracking_lists: 1, tracked_products: 0, scenarios: 0 })
    expect(overview.avg_scenario_margin).toBeNull()
    expect(overview.bsr_series).toEqual([])
    expect(overview.trend_distribution).toEqual({ rising: 0, stable: 0, declining: 0 })
  })
})
