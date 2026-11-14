import { Navigate } from 'react-router-dom'
import { AuthPageLayout } from '@/components/auth/AuthPageLayout'
import { RegisterForm } from '@/components/auth/RegisterForm'
import { useAuth } from '@/hooks/useAuth'

export default function RegisterPage() {
  const { user, isLoading } = useAuth()
  if (!isLoading && user) return <Navigate to="/dashboard" replace />
  return (
    <AuthPageLayout title="Create your account" subtitle="Start researching Amazon products">
      <RegisterForm />
    </AuthPageLayout>
  )
}
