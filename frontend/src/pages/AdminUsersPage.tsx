import { Link } from 'react-router-dom'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { UserTable } from '@/components/admin/UserTable'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/context/AuthContext'
import { useAdminUsers } from '@/hooks/useAdmin'

export default function AdminUsersPage() {
  const { user } = useAuth()
  const { data, loading, error, search, setSearch, page, setPage, update } = useAdminUsers()
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <PageWrapper>
      <main className="mx-auto max-w-5xl space-y-6 p-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-2xl font-bold">Users</h1>
          <Link to="/admin" className="text-sm text-primary hover:underline">
            Back to admin dashboard
          </Link>
        </div>
        <Input
          type="search"
          aria-label="Search users"
          placeholder="Search by email or name"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
        {loading && <p role="status">Loading users...</p>}
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
        {data && (
          <>
            <UserTable users={data.items} currentUserId={user?.id ?? null} onUpdate={update} />
            <nav aria-label="Pagination" className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                Page {page} of {totalPages} ({data.total} users)
              </span>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>
                  Previous
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page >= totalPages || loading}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                </Button>
              </div>
            </nav>
          </>
        )}
      </main>
    </PageWrapper>
  )
}
