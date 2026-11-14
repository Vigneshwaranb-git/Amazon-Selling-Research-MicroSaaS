import { Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

const FOCUS = 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

/** Minimal header for public pages that are not part of the authenticated shell. */
export function PublicHeader() {
  const { user } = useAuth()
  const target = user ? '/dashboard' : '/login'
  return (
    <header className="border-b bg-background/90">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <Link to={target} className={`rounded-md text-lg font-bold ${FOCUS}`}>
          AmzScoutIQ
        </Link>
        <nav aria-label="Account">
          <Link to={target} className={`rounded-md px-3 py-2 text-sm font-medium hover:bg-accent ${FOCUS}`}>
            {user ? 'Dashboard' : 'Login'}
          </Link>
        </nav>
      </div>
    </header>
  )
}
