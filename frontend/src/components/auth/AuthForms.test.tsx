import type { ReactNode } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
  })
})
