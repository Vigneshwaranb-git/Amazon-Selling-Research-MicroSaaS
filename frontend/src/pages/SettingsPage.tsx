import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { AsinImport } from '@/components/settings/AsinImport'
import { AvatarUploader } from '@/components/settings/AvatarUploader'
import { CostSheetImport } from '@/components/settings/CostSheetImport'
import { NotificationSettings } from '@/components/settings/NotificationSettings'
import { useAuth } from '@/hooks/useAuth'

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="space-y-3 rounded-2xl border p-6">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  )
}

export default function SettingsPage() {
  const { user } = useAuth()
  const displayName = user?.full_name || user?.email || 'User'
  return (
    <PageWrapper>
      <main className="mx-auto max-w-3xl space-y-6 p-8">
        <h1 className="text-2xl font-bold">Settings</h1>
        <Section title="Profile">
          <p className="text-sm">
            {user?.full_name ? `${user.full_name} - ` : ''}
            {user?.email}
          </p>
          <Link to="/profile" className="text-sm underline">
            Edit profile
          </Link>
        </Section>
        <Section title="Avatar">
          <AvatarUploader name={displayName} />
        </Section>
        <Section title="Notifications">
          <NotificationSettings />
        </Section>
        <Section title="Data import">
          <AsinImport />
          <hr />
          <CostSheetImport />
        </Section>
        <Section title="Billing">
          <Link to="/settings/billing" className="text-sm underline">
            Manage your subscription
          </Link>
        </Section>
      </main>
    </PageWrapper>
  )
}
