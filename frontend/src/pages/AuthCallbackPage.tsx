import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthPageLayout } from '@/components/auth/AuthPageLayout'
import { FormError } from '@/components/auth/FormField'
import { useAuth } from '@/hooks/useAuth'
import { storeTokens } from '@/services/authService'

/**
 * Landing page for the Google OAuth redirect. The backend sends the tokens in the URL
 * fragment (`#access_token=...&refresh_token=...`) so they never reach a server or log.
 */
export default function AuthCallbackPage() {
  const { refreshUser } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState('')

  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ''))
    const accessToken = params.get('access_token')
    const refreshToken = params.get('refresh_token')

    // Remove the tokens from the address bar and history straight away.
    window.history.replaceState(null, '', window.location.pathname)

    if (!accessToken || !refreshToken) {
      setError('Google sign-in failed. Please try again.')
      return
    }
    storeTokens({ access_token: accessToken, refresh_token: refreshToken })
    refreshUser()
      .then(() => navigate('/dashboard', { replace: true }))
      .catch(() => setError('Google sign-in failed. Please try again.'))
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
