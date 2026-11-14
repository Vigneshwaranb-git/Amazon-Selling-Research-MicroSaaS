import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { useAvatar } from '@/hooks/useAvatar'
import { UserAvatar } from '@/components/settings/UserAvatar'
import { DataSourceNotice } from '@/components/layout/DataSourceNotice'
import { cn } from '@/lib/utils'

interface NavItem {
  to: string
  label: string
  end?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/tracking-lists', label: 'Tracking Lists' },
  { to: '/calculator', label: 'Calculator', end: true },
  { to: '/calculator/saved', label: 'Saved Scenarios' },
  { to: '/analytics', label: 'Analytics' },
  { to: '/settings', label: 'Settings', end: true },
]

const ADMIN_ITEM: NavItem = { to: '/admin', label: 'Admin' }

const FOCUS = 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2'
const LINK_BASE = cn('rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent', FOCUS)

function navClass({ isActive }: { isActive: boolean }): string {
  return cn(LINK_BASE, isActive ? 'bg-accent text-accent-foreground' : 'text-muted-foreground')
}

export function AppLayout() {
  const { user, logout } = useAuth()
  const { url: avatarUrl } = useAvatar()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)

  // Close both menus whenever the route changes.
  useEffect(() => {
    setMenuOpen(false)
    setUserMenuOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (!menuOpen && !userMenuOpen) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuOpen(false)
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [menuOpen, userMenuOpen])

  useEffect(() => {
    if (!userMenuOpen) return
    const onPointer = (event: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) setUserMenuOpen(false)
    }
    document.addEventListener('mousedown', onPointer)
    return () => document.removeEventListener('mousedown', onPointer)
  }, [userMenuOpen])

  const items = user?.is_admin ? [...NAV_ITEMS, ADMIN_ITEM] : NAV_ITEMS
  const displayName = user?.full_name || user?.email || 'Account'

  const handleLogout = async (): Promise<void> => {
    setUserMenuOpen(false)
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen">
      <a
        href="#main-content"
        className={cn(
          'sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:text-sm',
          FOCUS,
        )}
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b bg-background/90 backdrop-blur">
        <div className="relative mx-auto flex max-w-7xl items-center gap-3 px-4 py-2">
          <Link to="/dashboard" className={cn('rounded-md text-lg font-bold', FOCUS)}>
            AmzScoutIQ
          </Link>
          <nav
            id="primary-nav"
            aria-label="Main"
            className={cn(
              'absolute inset-x-0 top-full flex-col gap-1 border-b bg-background p-3 md:static md:flex md:flex-1 md:flex-row md:border-0 md:bg-transparent md:p-0',
              menuOpen ? 'flex' : 'hidden',
            )}
          >
            {items.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end ?? false} className={navClass}>
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2 md:ml-0">
            <div className="relative" ref={userMenuRef}>
              <button
                type="button"
                aria-haspopup="menu"
                aria-expanded={userMenuOpen}
                aria-controls="user-menu"
                aria-label="User menu"
                onClick={() => setUserMenuOpen((open) => !open)}
                className={cn('rounded-full', FOCUS)}
              >
                <UserAvatar url={avatarUrl} name={displayName} className="size-9 text-sm" />
              </button>
              {userMenuOpen && (
                <div
                  id="user-menu"
                  role="menu"
                  aria-label="User menu"
                  className="absolute right-0 mt-2 flex w-44 flex-col rounded-md border bg-background p-1 shadow-md"
                >
                  <Link role="menuitem" to="/profile" className={LINK_BASE}>
                    Profile
                  </Link>
                  <Link role="menuitem" to="/settings/billing" className={LINK_BASE}>
                    Billing
                  </Link>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => void handleLogout()}
                    className={cn(LINK_BASE, 'text-left')}
                  >
                    Logout
                  </button>
                </div>
              )}
            </div>
            <button
              type="button"
              aria-expanded={menuOpen}
              aria-controls="primary-nav"
              aria-label="Toggle navigation menu"
              onClick={() => setMenuOpen((open) => !open)}
              className={cn('rounded-md p-2 hover:bg-accent md:hidden', FOCUS)}
            >
              {menuOpen ? <X aria-hidden="true" className="size-5" /> : <Menu aria-hidden="true" className="size-5" />}
            </button>
          </div>
        </div>
      </header>
      <div id="main-content" tabIndex={-1} className="outline-none">
        <Outlet />
      </div>
      <footer className="mx-auto max-w-7xl border-t px-4 py-4">
        <DataSourceNotice />
      </footer>
    </div>
  )
}
