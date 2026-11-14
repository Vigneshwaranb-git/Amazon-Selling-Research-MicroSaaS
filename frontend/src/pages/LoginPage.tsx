import { Navigate, useSearchParams } from 'react-router-dom'
import { AuthPageLayout } from '@/components/auth/AuthPageLayout'
import { LoginForm } from '@/components/auth/LoginForm'
import { FormError } from '@/components/auth/FormField'
import { useAuth } from '@/hooks/useAuth'

export default function LoginPage() {
  const { user, isLoading } = useAuth()
  const [params] = useSearchParams()
  const oauthError = params.get('error')

  if (!isLoading && user) return <Navigate to="/dashboard" replace />

  return (
    <AuthPageLayout title="Welcome back" subtitle="Sign in to AmzScoutIQ">
      {oauthError && (
        <div className="mb-4">
          <FormError message="Google sign-in failed. Please try again." />
        </div>
      )}
      <LoginForm />
    </AuthPageLayout>
  )
}
