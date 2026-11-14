import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AuthCallbackPage from '@/pages/AuthCallbackPage'
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from '@/services/api'

const refreshUser = vi.fn<() => Promise<void>>()
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ refreshUser }) }))

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/auth/callback']}>
      <Routes>
        <Route path="/auth/callback" element={<AuthCallbackPage />} />
        <Route path="/dashboard" element={<div>DASHBOARD</div>} />
        <Route path="/login" element={<div>LOGIN</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

function setHash(hash: string) {
  window.history.replaceState(null, '', `/auth/callback${hash}`)
}

beforeEach(() => {
  localStorage.clear()
  refreshUser.mockReset()
})
afterEach(() => {
  window.history.replaceState(null, '', '/')
})

describe('AuthCallbackPage', () => {
  it('stores tokens from the fragment, clears the hash, and goes to the dashboard', async () => {
    refreshUser.mockResolvedValue()
    setHash('#access_token=acc.123&refresh_token=ref.456')
    renderPage()
    expect(await screen.findByText('DASHBOARD')).toBeInTheDocument()
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBe('acc.123')
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe('ref.456')
    expect(window.location.hash).toBe('')
    expect(window.location.href).not.toContain('acc.123')
    expect(refreshUser).toHaveBeenCalledTimes(1)
  })

  it('clears the hash immediately even before the user loads', async () => {
    refreshUser.mockReturnValue(new Promise(() => {}))
    setHash('#access_token=a&refresh_token=b')
    renderPage()
    await waitFor(() => expect(window.location.hash).toBe(''))
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBe('a')
  })

  it.each([
    ['no fragment', ''],
    ['missing refresh token', '#access_token=a'],
    ['missing access token', '#refresh_token=b'],
    ['empty values', '#access_token=&refresh_token='],
    ['error fragment', '#error=access_denied'],
  ])('shows an error and stores nothing when %s', async (_name, hash) => {
    setHash(hash)
    renderPage()
    expect(await screen.findByText(/Google sign-in failed/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to sign in/i })).toHaveAttribute('href', '/login')
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull()
    expect(refreshUser).not.toHaveBeenCalled()
    expect(window.location.hash).toBe('')
  })

  it('shows an error when loading the user fails', async () => {
    refreshUser.mockImplementation(async () => { throw new Error('401') })
    setHash('#access_token=a&refresh_token=b')
    renderPage()
    expect(await screen.findByText(/Google sign-in failed/i)).toBeInTheDocument()
    expect(screen.queryByText('DASHBOARD')).not.toBeInTheDocument()
  })

  it('decodes url-encoded token values', async () => {
    refreshUser.mockResolvedValue()
    setHash('#access_token=a%2Bb&refresh_token=c%3Dd')
    renderPage()
    await screen.findByText('DASHBOARD')
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBe('a+b')
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe('c=d')
  })
})
