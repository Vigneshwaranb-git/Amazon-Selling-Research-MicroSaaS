import { render, screen, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/context/AuthContext'
import { useAuth } from '@/hooks/useAuth'

const refreshSession = vi.fn<() => Promise<string>>()
const getMe = vi.fn()
vi.mock('@/services/api', () => ({ refreshSession: () => refreshSession() }))
vi.mock('@/services/authService', () => ({ getMe: () => getMe() }))

function Probe() {
  const { user, isLoading } = useAuth()
  return <p data-testid="s">{isLoading ? 'loading' : (user?.email ?? 'anon')}</p>
}

const renderProvider = () =>
  render(
    <StrictMode>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </StrictMode>,
  )

beforeEach(() => {
  refreshSession.mockReset()
  getMe.mockReset()
})

describe('AuthProvider bootstrap', () => {
  it('stays loading, refreshes, then loads the user', async () => {
    refreshSession.mockResolvedValue('tok')
    getMe.mockResolvedValue({ id: 1, email: 'a@b.co' })
    renderProvider()
    expect(screen.getByTestId('s')).toHaveTextContent('loading')
    await waitFor(() => expect(screen.getByTestId('s')).toHaveTextContent('a@b.co'))
  })

  it('treats a failed refresh as logged out without fetching the user', async () => {
    refreshSession.mockRejectedValue(new Error('401'))
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('s')).toHaveTextContent('anon'))
    expect(getMe).not.toHaveBeenCalled()
  })
})
