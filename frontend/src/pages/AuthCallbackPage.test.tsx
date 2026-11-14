import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AuthCallbackPage from '@/pages/AuthCallbackPage'

const refreshUser = vi.fn<() => Promise<void>>()
const refreshSession = vi.fn<() => Promise<string>>()
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ refreshUser }) }))
vi.mock('@/services/api', () => ({ refreshSession: () => refreshSession() }))

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

beforeEach(() => {
  localStorage.clear()
  refreshUser.mockReset()
  refreshSession.mockReset()
})

describe('AuthCallbackPage', () => {
  it('bootstraps the session from the cookie then goes to the dashboard', async () => {
    refreshSession.mockResolvedValue('tok')
    refreshUser.mockResolvedValue()
    renderPage()
    expect(await screen.findByText('DASHBOARD')).toBeInTheDocument()
    expect(refreshSession).toHaveBeenCalledTimes(1)
    expect(refreshUser).toHaveBeenCalledTimes(1)
    expect(localStorage.length).toBe(0)
  })

  it('shows an error when the refresh fails', async () => {
    refreshSession.mockRejectedValue(new Error('401'))
    renderPage()
    expect(await screen.findByText(/Google sign-in failed/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to sign in/i })).toHaveAttribute('href', '/login')
    expect(refreshUser).not.toHaveBeenCalled()
  })

  it('shows an error when loading the user fails', async () => {
    refreshSession.mockResolvedValue('tok')
    refreshUser.mockRejectedValue(new Error('401'))
    renderPage()
    expect(await screen.findByText(/Google sign-in failed/i)).toBeInTheDocument()
    expect(screen.queryByText('DASHBOARD')).not.toBeInTheDocument()
  })
})
