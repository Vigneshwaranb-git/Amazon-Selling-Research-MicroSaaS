import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { useAuth } from '@/context/AuthContext'
import type { User } from '@/types'

vi.mock('@/context/AuthContext')
vi.mock('@/hooks/useAvatar', () => ({ useAvatar: () => ({ url: null }) }))

const mockedUseAuth = vi.mocked(useAuth)
const logout = vi.fn<() => Promise<void>>()

function setUser(overrides: Partial<User>): void {
  const user = { id: 1, email: 'a@b.co', full_name: 'Ada Lovelace', is_admin: false, ...overrides } as User
  mockedUseAuth.mockReturnValue({ user, isLoading: false, logout } as unknown as ReturnType<typeof useAuth>)
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<h1>Dash page</h1>} />
          <Route path="/analytics" element={<h1>Analytics page</h1>} />
        </Route>
        <Route path="/login" element={<h1>Login page</h1>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AppLayout', () => {
  beforeEach(() => {
    logout.mockReset()
    logout.mockResolvedValue(undefined)
    setUser({})
  })

  it('renders the main nav, skip link and routed content', () => {
    renderAt('/dashboard')
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '#main-content')
    expect(screen.getByRole('link', { name: 'AmzScoutIQ' })).toHaveAttribute('href', '/dashboard')
    expect(screen.getByRole('heading', { name: 'Dash page' })).toBeInTheDocument()
  })

  it('hides the Admin link for non-admins and shows it for admins', () => {
    const { unmount } = renderAt('/dashboard')
    expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument()
    unmount()
    setUser({ is_admin: true })
    renderAt('/dashboard')
    expect(screen.getByRole('link', { name: 'Admin' })).toHaveAttribute('href', '/admin')
  })

  it('marks only the active link with aria-current', () => {
    renderAt('/analytics')
    expect(screen.getByRole('link', { name: 'Analytics' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Dashboard' })).not.toHaveAttribute('aria-current')
  })

  it('toggles the mobile menu and closes it on Escape', async () => {
    const user = userEvent.setup()
    renderAt('/dashboard')
    const toggle = screen.getByRole('button', { name: 'Toggle navigation menu' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(toggle).toHaveAttribute('aria-controls', 'primary-nav')
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await user.keyboard('{Escape}')
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
  })

  it('closes the mobile menu on route change', async () => {
    const user = userEvent.setup()
    renderAt('/dashboard')
    const toggle = screen.getByRole('button', { name: 'Toggle navigation menu' })
    await user.click(toggle)
    await user.click(screen.getByRole('link', { name: 'Analytics' }))
    expect(screen.getByRole('heading', { name: 'Analytics page' })).toBeInTheDocument()
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
  })

  it('offers Profile and Billing in the user menu, closing on Escape', async () => {
    const user = userEvent.setup()
    renderAt('/dashboard')
    await user.click(screen.getByRole('button', { name: 'User menu' }))
    expect(screen.getByRole('menuitem', { name: 'Profile' })).toHaveAttribute('href', '/profile')
    expect(screen.getByRole('menuitem', { name: 'Billing' })).toHaveAttribute('href', '/settings/billing')
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('menuitem', { name: 'Profile' })).not.toBeInTheDocument()
  })

  it('logs out through useAuth and navigates to login', async () => {
    const user = userEvent.setup()
    renderAt('/dashboard')
    await user.click(screen.getByRole('button', { name: 'User menu' }))
    await user.click(screen.getByRole('menuitem', { name: 'Logout' }))
    expect(logout).toHaveBeenCalledTimes(1)
    expect(await screen.findByRole('heading', { name: 'Login page' })).toBeInTheDocument()
  })
})
