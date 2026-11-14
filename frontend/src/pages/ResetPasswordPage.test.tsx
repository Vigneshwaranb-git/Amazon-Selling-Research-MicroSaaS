import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ForgotPasswordPage from '@/pages/ForgotPasswordPage'
import ResetPasswordPage from '@/pages/ResetPasswordPage'

const resetPassword = vi.fn<(token: string, pw: string) => Promise<void>>()
const forgotPassword = vi.fn<(email: string) => Promise<void>>()

vi.mock('@/services/authService', () => ({
  resetPassword: (t: string, p: string) => resetPassword(t, p),
  forgotPassword: (e: string) => forgotPassword(e),
}))

function Where() {
  const loc = useLocation()
  return <p data-testid="loc">{loc.pathname + loc.search}</p>
}

const renderAt = (url: string) =>
  render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/reset-password" element={<><ResetPasswordPage /><Where /></>} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      </Routes>
    </MemoryRouter>,
  )

beforeEach(() => {
  resetPassword.mockReset()
  forgotPassword.mockReset()
})

describe('ResetPasswordPage', () => {
  it('shows an invalid-link message without a token', () => {
    renderAt('/reset-password')
    expect(screen.getByText(/invalid or incomplete/i)).toBeInTheDocument()
  })

  it('validates length and confirmation', async () => {
    renderAt('/reset-password?token=abc')
    await userEvent.type(screen.getByLabelText('New password'), 'short')
    await userEvent.type(screen.getByLabelText('Confirm password'), 'other')
    await userEvent.click(screen.getByRole('button', { name: 'Reset password' }))
    expect(screen.getByText('Password must be at least 8 characters')).toBeInTheDocument()
    expect(screen.getByText('Passwords do not match')).toBeInTheDocument()
    expect(resetPassword).not.toHaveBeenCalled()
  })

  it('submits and shows the success state linking to login', async () => {
    resetPassword.mockResolvedValue()
    renderAt('/reset-password?token=abc')
    await userEvent.type(screen.getByLabelText('New password'), 'newpass123')
    await userEvent.type(screen.getByLabelText('Confirm password'), 'newpass123')
    await userEvent.click(screen.getByRole('button', { name: 'Reset password' }))
    await waitFor(() => expect(resetPassword).toHaveBeenCalledWith('abc', 'newpass123'))
    expect(await screen.findByText(/has been reset/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to sign in' })).toHaveAttribute('href', '/login')
  })

  it('shows an error when the API rejects', async () => {
    resetPassword.mockRejectedValue(new Error('x'))
    renderAt('/reset-password?token=abc')
    await userEvent.type(screen.getByLabelText('New password'), 'newpass123')
    await userEvent.type(screen.getByLabelText('Confirm password'), 'newpass123')
    await userEvent.click(screen.getByRole('button', { name: 'Reset password' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})

describe('ForgotPasswordPage', () => {
  it('redirects legacy ?token= links to /reset-password', () => {
    renderAt('/forgot-password?token=old%20tok')
    expect(screen.getByTestId('loc')).toHaveTextContent('/reset-password?token=old%20tok')
  })
  it('shows the email form without a token', () => {
    renderAt('/forgot-password')
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
  })
})
