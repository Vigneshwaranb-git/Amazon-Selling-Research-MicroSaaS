import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { getErrorMessage } from '@/lib/errors'
import { ConfirmDialog } from '@/components/admin/ConfirmDialog'
import type { AdminUser, AdminUserUpdate } from '@/types/admin'

interface UserTableProps {
  users: AdminUser[]
  currentUserId: number | null
  onUpdate: (id: number, change: AdminUserUpdate) => Promise<void>
}

type ActionKind = 'activate' | 'deactivate' | 'promote' | 'demote'

interface PendingAction {
  user: AdminUser
  kind: ActionKind
}

const ACTION_CHANGE: Record<ActionKind, AdminUserUpdate> = {
  activate: { is_active: true },
  deactivate: { is_active: false },
  promote: { is_admin: true },
  demote: { is_admin: false },
}

const ACTION_VERB: Record<ActionKind, string> = {
  activate: 'Activate',
  deactivate: 'Deactivate',
  promote: 'Promote to admin',
  demote: 'Demote from admin',
}

export function UserTable({ users, currentUserId, onUpdate }: UserTableProps) {
  const [pending, setPending] = useState<PendingAction | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const close = (): void => {
    setPending(null)
    setError(null)
  }

  const confirm = async (): Promise<void> => {
    if (!pending) return
    setBusy(true)
    setError(null)
    try {
      await onUpdate(pending.user.id, ACTION_CHANGE[pending.kind])
      setPending(null)
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Could not update the user.'))
    } finally {
      setBusy(false)
    }
  }

  if (users.length === 0) {
    return <p className="text-sm text-muted-foreground">No users found.</p>
  }

  return (
    <>
      <div className="overflow-x-auto rounded-xl border">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Users</caption>
          <thead className="bg-muted text-muted-foreground">
            <tr>
              <th scope="col" className="p-3">User</th>
              <th scope="col" className="p-3">Plan</th>
              <th scope="col" className="p-3">Status</th>
              <th scope="col" className="p-3">Role</th>
              <th scope="col" className="p-3">Joined</th>
              <th scope="col" className="p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => {
              const isSelf = u.id === currentUserId
              return (
                <tr key={u.id} className="border-t">
                  <td className="p-3">
                    <div className="font-medium">{u.email}</div>
                    {u.full_name && <div className="text-xs text-muted-foreground">{u.full_name}</div>}
                  </td>
                  <td className="p-3 capitalize">{u.plan}</td>
                  <td className="p-3">{u.is_active ? 'Active' : 'Inactive'}</td>
                  <td className="p-3">{u.is_admin ? 'Admin' : 'User'}</td>
                  <td className="p-3">{u.created_at.slice(0, 10)}</td>
                  <td className="p-3">
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={isSelf && u.is_active}
                        title={isSelf ? 'You cannot deactivate your own account' : undefined}
                        aria-label={`${u.is_active ? 'Deactivate' : 'Activate'} ${u.email}`}
                        onClick={() => setPending({ user: u, kind: u.is_active ? 'deactivate' : 'activate' })}
                      >
                        {u.is_active ? 'Deactivate' : 'Activate'}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={isSelf && u.is_admin}
                        title={isSelf ? 'You cannot demote yourself' : undefined}
                        aria-label={`${u.is_admin ? 'Demote' : 'Promote'} ${u.email}`}
                        onClick={() => setPending({ user: u, kind: u.is_admin ? 'demote' : 'promote' })}
                      >
                        {u.is_admin ? 'Demote' : 'Promote'}
                      </Button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {pending && (
        <ConfirmDialog
          title={`${ACTION_VERB[pending.kind]}?`}
          description={`${ACTION_VERB[pending.kind]}: ${pending.user.email}. You can change this later.`}
          confirmLabel={ACTION_VERB[pending.kind]}
          destructive={pending.kind === 'deactivate' || pending.kind === 'demote'}
          busy={busy}
          error={error}
          onConfirm={() => void confirm()}
          onCancel={close}
        />
      )}
    </>
  )
}
