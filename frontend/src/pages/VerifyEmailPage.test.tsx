import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StrictMode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import VerifyEmailPage from '@/pages/VerifyEmailPage'

const verifyEmail = vi.fn<(t: string) => Promise<string>>()
const resendVerification = vi.fn<(e: string) => Promise<string>>()
vi.mock('@/services/authService', () => ({
  verifyEmail: (t: string) => verifyEmail(t),
  resendVerification: (e: string) => resendVerification(e),
}))

const renderAt = (url: string) =>
  render(
    <StrictMode>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/verify-email" element={<VerifyEmailPage />} />
        </Routes>
      </MemoryRouter>
    </StrictMode>,
  )

beforeEach(() => {
  verifyEmail.mockReset()
  resendVerification.mockReset()
})

describe('VerifyEmailPage', () => {
  it('shows loading, then success with a sign-in link, submitting once', async () => {
    verifyEmail.mockResolvedValue('ok')
    renderAt('/verify-email?token=abc')
    expect(screen.getByText(/Verifying your email/)).toBeInTheDocument()
    expect(await screen.findByText(/Your email is verified/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /go to sign in/i })).toHaveAttribute('href', '/login')
    expect(verifyEmail).toHaveBeenCalledTimes(1)
    expect(verifyEmail).toHaveBeenCalledWith('abc')
  })

  it('shows an error for an invalid token and lets the user resend', async () => {
    verifyEmail.mockRejectedValue(new Error('400'))
    resendVerification.mockResolvedValue('sent')
    renderAt('/verify-email?token=bad')
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Email'), 'a@b.com')
    await userEvent.click(screen.getByRole('button', { name: /resend verification email/i }))
    expect(resendVerification).toHaveBeenCalledWith('a@b.com')
    expect(await screen.findByText(/new email is on its way/i)).toBeInTheDocument()
  })

  it('shows an error without calling the API when the token is missing', () => {
    renderAt('/verify-email')
    expect(screen.getByRole('alert')).toHaveTextContent(/invalid or incomplete/i)
    expect(verifyEmail).not.toHaveBeenCalled()
  })
})
