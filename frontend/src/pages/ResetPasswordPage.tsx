import { Link, useSearchParams } from 'react-router-dom'
import { AuthPageLayout } from '@/components/auth/AuthPageLayout'
import { ResetPasswordForm } from '@/components/auth/ResetPasswordForm'

export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token')
  return (
    <AuthPageLayout title="Set a new password" subtitle="Choose a new password for your account">
      {token ? (
        <ResetPasswordForm token={token} />
      ) : (
        <div role="alert" className="space-y-4 text-center">
          <p className="text-sm text-red-500">This reset link is invalid or incomplete.</p>
          <Link to="/forgot-password" className="underline">
            Request a new reset link
          </Link>
        </div>
      )}
    </AuthPageLayout>
  )
}
