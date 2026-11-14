import type { ReactNode } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, type AxiosResponse } from 'axios'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LoginForm } from '@/components/auth/LoginForm'
import { RegisterForm } from '@/components/auth/RegisterForm'

interface RegisterArgs {
  email: string
  password: string
  full_name: string
}

const login = vi.fn<(email: string, password: string) => Promise<void>>()
const register = vi.fn<(p: RegisterArgs) => Promise<void>>()

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ login, register }),
}))

const resendVerification = vi.fn<(email: string) => Promise<string>>()
vi.mock('@/services/authService', () => ({
  resendVerification: (e: string) => resendVerification(e),
  getGoogleLoginUrl: () => '/google',
}))

function apiError(status: number, code: string): AxiosError {
  const response = { status, data: { error: { code, message: 'x' } } } as AxiosResponse
  return new AxiosError('fail', String(status), undefined, null, response)
}

const wrap = (ui: ReactNode) => render(<MemoryRouter>{ui}</MemoryRouter>)

describe('LoginForm', () => {
  beforeEach(() => {
    login.mockReset()
  })

  it('shows validation errors and does not submit an empty form', async () => {
    wrap(<LoginForm />)
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(screen.getByText('Email is required')).toBeInTheDocument()
    expect(screen.getByText('Password is required')).toBeInTheDocument()
    expect(login).not.toHaveBeenCalled()
  })

  it('submits credentials', async () => {
    login.mockResolvedValue()
    wrap(<LoginForm />)
    await userEvent.type(screen.getByLabelText('Email'), 'a@b.com')
    await userEvent.type(screen.getByLabelText('Password'), 'secret123')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    await waitFor(() => expect(login).toHaveBeenCalledWith('a@b.com', 'secret123'))
  })

  it('shows an error when login fails', async () => {
    login.mockRejectedValue(new Error('bad'))
    wrap(<LoginForm />)
    await userEvent.type(screen.getByLabelText('Email'), 'a@b.com')
    await userEvent.type(screen.getByLabelText('Password'), 'secret123')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Login failed')
  })

  it('offers to resend the verification email when the email is not verified', async () => {
    login.mockRejectedValue(apiError(403, 'EMAIL_NOT_VERIFIED'))
    resendVerification.mockResolvedValue('sent')
    wrap(<LoginForm />)
    await userEvent.type(screen.getByLabelText('Email'), 'a@b.com')
    await userEvent.type(screen.getByLabelText('Password'), 'secret123')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/not verified/i)
    await userEvent.click(screen.getByRole('button', { name: /resend verification email/i }))
    expect(resendVerification).toHaveBeenCalledWith('a@b.com')
    expect(await screen.findByText(/new email is on its way/i)).toBeInTheDocument()
  })

  it('shows a friendly message when resending is rate limited', async () => {
    login.mockRejectedValue(apiError(403, 'EMAIL_NOT_VERIFIED'))
    resendVerification.mockRejectedValue(apiError(429, 'RATE_LIMITED'))
    wrap(<LoginForm />)
    await userEvent.type(screen.getByLabelText('Email'), 'a@b.com')
    await userEvent.type(screen.getByLabelText('Password'), 'secret123')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    await userEvent.click(await screen.findByRole('button', { name: /resend verification email/i }))
    expect(await screen.findByText(/too many requests/i)).toBeInTheDocument()
  })
})

describe('RegisterForm', () => {
  beforeEach(() => {
    register.mockReset()
  })

  it('validates password length and confirmation', async () => {
    wrap(<RegisterForm />)
    await userEvent.type(screen.getByLabelText('Full name'), 'Jane')
    await userEvent.type(screen.getByLabelText('Email'), 'jane@x.com')
    await userEvent.type(screen.getByLabelText('Password'), 'short')
    await userEvent.type(screen.getByLabelText('Confirm password'), 'other')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(screen.getByText('Password must be at least 8 characters')).toBeInTheDocument()
    expect(screen.getByText('Passwords do not match')).toBeInTheDocument()
    expect(register).not.toHaveBeenCalled()
  })

  it('submits a valid registration', async () => {
    register.mockResolvedValue()
    wrap(<RegisterForm />)
    await userEvent.type(screen.getByLabelText('Full name'), 'Jane')
    await userEvent.type(screen.getByLabelText('Email'), 'jane@x.com')
    await userEvent.type(screen.getByLabelText('Password'), 'password123')
    await userEvent.type(screen.getByLabelText('Confirm password'), 'password123')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    await waitFor(() =>
      expect(register).toHaveBeenCalledWith({ email: 'jane@x.com', password: 'password123', full_name: 'Jane' }),
    )
    expect(await screen.findByText('Check your email to verify your account')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /resend verification email/i })).toBeInTheDocument()
  })
})
