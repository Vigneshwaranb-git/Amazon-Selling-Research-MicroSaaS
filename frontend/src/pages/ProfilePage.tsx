import { useNavigate } from 'react-router-dom'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { GlassCard } from '@/components/ui/GlassCard'
import { ProfileForm } from '@/components/auth/ProfileForm'
import { useAuth } from '@/hooks/useAuth'

export default function ProfilePage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const onLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  if (!user) return null

  return (
    <PageWrapper>
      <main className="mx-auto max-w-xl p-8">
        <GlassCard>
          <h1 className="mb-6 text-2xl font-bold">Your profile</h1>
          <ProfileForm />
          <button type="button" onClick={onLogout} className="mt-6 text-sm underline">
            Sign out
          </button>
        </GlassCard>
      </main>
    </PageWrapper>
  )
}
