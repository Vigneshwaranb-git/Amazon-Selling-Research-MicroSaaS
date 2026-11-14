import { Navigate, useSearchParams } from 'react-router-dom'
import { AuthPageLayout } from '@/components/auth/AuthPageLayout'
import { ForgotPasswordForm } from '@/components/auth/ForgotPasswordForm'

export default function ForgotPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token')
  // Old emailed links pointed at /forgot-password?token=...
  if (token) return <Navigate to={`/reset-password?token=${encodeURIComponent(token)}`} replace />
  return (
    <AuthPageLayout title="Forgot password" subtitle="We will email you a reset link">
      <ForgotPasswordForm />
    </AuthPageLayout>
  )
}
