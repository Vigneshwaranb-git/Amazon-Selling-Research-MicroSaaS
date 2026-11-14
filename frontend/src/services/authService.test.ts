import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '@/services/api'
import { updateMe } from '@/services/authService'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
  ACCESS_TOKEN_KEY: 'access_token',
  REFRESH_TOKEN_KEY: 'refresh_token',
}))
const mocked = vi.mocked(api)

const user = {
  id: 1,
  email: 'a@b.co',
  full_name: 'Ada',
  is_active: true,
  is_admin: false,
  created_at: '2026-01-01T00:00:00Z',
}

beforeEach(() => {
  mocked.put.mockReset()
  localStorage.clear()
})

describe('updateMe', () => {
  it('stores the fresh token pair returned after a password change', async () => {
    localStorage.setItem('refresh_token', 'old-refresh')
    mocked.put.mockResolvedValue({
      data: { ...user, tokens: { access_token: 'new-access', refresh_token: 'new-refresh' } },
    })

    const result = await updateMe({ current_password: 'old', password: 'new-password-1' })

    expect(localStorage.getItem('access_token')).toBe('new-access')
    expect(localStorage.getItem('refresh_token')).toBe('new-refresh')
    expect(result).toEqual(user)
    expect(result).not.toHaveProperty('tokens')
  })

  it('leaves stored tokens alone when no tokens are returned', async () => {
    localStorage.setItem('refresh_token', 'keep-me')
    mocked.put.mockResolvedValue({ data: { ...user, tokens: null } })

    await updateMe({ full_name: 'Ada' })

    expect(localStorage.getItem('refresh_token')).toBe('keep-me')
  })
})
