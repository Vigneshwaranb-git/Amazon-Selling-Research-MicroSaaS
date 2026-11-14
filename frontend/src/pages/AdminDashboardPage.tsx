import { Link } from 'react-router-dom'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { StatsCards } from '@/components/admin/StatsCards'
import { useAdminStats } from '@/hooks/useAdmin'

export default function AdminDashboardPage() {
  const { stats, loading, error } = useAdminStats()
  return (
    <PageWrapper>
      <main className="mx-auto max-w-5xl space-y-6 p-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-2xl font-bold">Admin Dashboard</h1>
          <Link to="/admin/users" className="text-sm text-primary hover:underline">
            Manage users
          </Link>
        </div>
        {loading && <p role="status">Loading stats...</p>}
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
        {stats && <StatsCards stats={stats} />}
      </main>
    </PageWrapper>
  )
}
