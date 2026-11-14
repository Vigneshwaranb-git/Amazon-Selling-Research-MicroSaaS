import { useNavigate } from 'react-router-dom'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { GlassCard } from '@/components/ui/GlassCard'
import { ProfileForm } from '@/components/auth/ProfileForm'
import { UserAvatar } from '@/components/settings/UserAvatar'
import { useAuth } from '@/hooks/useAuth'
import { useAvatar } from '@/hooks/useAvatar'

export default function ProfilePage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { url: avatarUrl } = useAvatar()

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
          <div className="mb-6">
            <UserAvatar url={avatarUrl} name={user.full_name || user.email} />
          </div>
          <ProfileForm />
          <button type="button" onClick={onLogout} className="mt-6 text-sm underline">
            Sign out
          </button>
        </GlassCard>
      </main>
    </PageWrapper>
  )
}
