import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthPageLayout } from '@/components/auth/AuthPageLayout'
import { FormError } from '@/components/auth/FormField'
import { useAuth } from '@/hooks/useAuth'
import { refreshSession } from '@/services/api'

/**
 * Landing page for the Google OAuth redirect. The backend has already set the HttpOnly refresh
 * cookie, so no tokens travel in the URL: we exchange the cookie for an access token and load the user.
 */
export default function AuthCallbackPage() {
  const { refreshUser } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    refreshSession()
      .then(() => refreshUser())
      .then(() => {
        if (!cancelled) navigate('/dashboard', { replace: true })
      })
      .catch(() => {
        if (!cancelled) setError('Google sign-in failed. Please try again.')
      })
    return () => {
      cancelled = true
    }
  }, [refreshUser, navigate])

  return (
    <AuthPageLayout title="Signing you in" subtitle="Completing Google sign-in...">
      {error && (
        <div className="space-y-4">
          <FormError message={error} />
          <Link to="/login" className="text-sm underline">
            Back to sign in
          </Link>
        </div>
      )}
    </AuthPageLayout>
  )
}
