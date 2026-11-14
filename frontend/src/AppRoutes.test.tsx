import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppRoutes } from '@/App'
import { useAuth } from '@/context/AuthContext'
import type { User } from '@/types'

vi.mock('@/context/AuthContext')
vi.mock('@/hooks/useAvatar', () => ({ useAvatar: () => ({ url: null }) }))
vi.mock('@/hooks/useSubscription', () => ({ useSubscription: () => ({ subscription: null }) }))
vi.mock('@/pages/LoginPage', () => ({ default: () => <h1>Login page</h1> }))
vi.mock('@/pages/DashboardPage', () => ({ default: () => <h1>Dashboard page</h1> }))
vi.mock('@/pages/AdminDashboardPage', () => ({ default: () => <h1>Admin page</h1> }))

const mockedUseAuth = vi.mocked(useAuth)

function renderAt(path: string, user: Partial<User> | null) {
  mockedUseAuth.mockReturnValue({
    user: user ? ({ id: 1, email: 'a@b.co', full_name: 'Ada', is_admin: false, ...user } as User) : null,
    isLoading: false,
    logout: vi.fn(),
  } as unknown as ReturnType<typeof useAuth>)
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  )
}

describe('AppRoutes', () => {
  it('does not render the app nav on the login page', () => {
    renderAt('/login', null)
    expect(screen.getByRole('heading', { name: 'Login page' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument()
  })

  it('shows only a minimal public header on pricing', () => {
    renderAt('/pricing', null)
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Login' })).toHaveAttribute('href', '/login')
  })

  it('links pricing back to the dashboard when signed in', () => {
    renderAt('/pricing', {})
    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('href', '/dashboard')
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument()
  })

  it('redirects anonymous users from protected routes to login', () => {
    renderAt('/dashboard', null)
    expect(screen.getByRole('heading', { name: 'Login page' })).toBeInTheDocument()
  })

  it('wraps protected pages in the app layout', () => {
    renderAt('/dashboard', {})
    expect(screen.getByRole('heading', { name: 'Dashboard page' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
  })

  it('keeps admin routes admin-only', () => {
    renderAt('/admin', {})
    expect(screen.queryByRole('heading', { name: 'Admin page' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Dashboard page' })).toBeInTheDocument()
  })

  it('renders admin pages for admins', () => {
    renderAt('/admin', { is_admin: true })
    expect(screen.getByRole('heading', { name: 'Admin page' })).toBeInTheDocument()
  })
})
