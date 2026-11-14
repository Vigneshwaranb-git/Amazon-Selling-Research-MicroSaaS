import { beforeEach, describe, expect, it, vi } from 'vitest'
import api, { getAccessToken, setAccessToken } from '@/services/api'
import { login, logout, resendVerification, updateMe, verifyEmail } from '@/services/authService'

vi.mock('@/services/api', () => {
  let token: string | null = null
  return {
    default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
    getAccessToken: () => token,
    setAccessToken: (t: string | null) => {
      token = t
    },
  }
})
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
  vi.clearAllMocks()
  setAccessToken(null)
  localStorage.clear()
})

describe('authService', () => {
  it('login keeps the access token in memory and never in storage', async () => {
    mocked.post.mockResolvedValue({ data: { access_token: 'acc', token_type: 'bearer' } })
    await login('a@b.co', 'pw')
    expect(getAccessToken()).toBe('acc')
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })

  it('logout posts without a body and clears the token even on failure', async () => {
    setAccessToken('acc')
    mocked.post.mockRejectedValue(new Error('network'))
    await logout()
    expect(mocked.post).toHaveBeenCalledWith('/auth/logout')
    expect(getAccessToken()).toBeNull()
  })

  it('updateMe returns the plain user', async () => {
    mocked.put.mockResolvedValue({ data: user })
    expect(await updateMe({ full_name: 'Ada' })).toEqual(user)
    expect(localStorage.length).toBe(0)
  })

  it('verifyEmail and resendVerification post to the right endpoints', async () => {
    mocked.post.mockResolvedValue({ data: { message: 'ok' } })
    expect(await verifyEmail('tok')).toBe('ok')
    expect(mocked.post).toHaveBeenCalledWith('/auth/verify-email', { token: 'tok' })
    expect(await resendVerification('a@b.co')).toBe('ok')
    expect(mocked.post).toHaveBeenCalledWith('/auth/resend-verification', { email: 'a@b.co' })
  })
})
