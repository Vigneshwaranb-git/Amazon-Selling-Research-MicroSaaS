import { useState, type FormEvent } from 'react'
import { GradientButton } from '@/components/ui/GradientButton'
import { FormError, FormField } from '@/components/auth/FormField'
import { validatePassword } from '@/components/auth/validation'
import { useAuth } from '@/hooks/useAuth'
import { getErrorMessage } from '@/lib/errors'

export function ProfileForm() {
  const { user, updateProfile } = useAuth()
  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [currentPassword, setCurrentPassword] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<{ fullName?: string; currentPassword?: string; password?: string }>({})
  const [formError, setFormError] = useState('')
  const [saved, setSaved] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setSaved(false)
    setFormError('')
    const next = {
      fullName: fullName.trim() ? undefined : 'Full name is required',
      currentPassword: password && !currentPassword ? 'Current password is required' : undefined,
      password: password ? validatePassword(password) : undefined,
    }
    setErrors(next)
    if (next.fullName || next.currentPassword || next.password) return
    setSubmitting(true)
    try {
      await updateProfile({ full_name: fullName.trim(), ...(password ? { current_password: currentPassword, password } : {}) })
      setCurrentPassword('')
      setPassword('')
      setSaved(true)
    } catch (err) {
      setFormError(getErrorMessage(err, 'Could not update profile.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {formError && <FormError message={formError} />}
      {saved && (
        <p role="status" className="rounded-md bg-green-500/10 px-3 py-2 text-sm text-green-600">
          Profile updated.
        </p>
      )}
      <FormField id="email" label="Email" type="email" value={user?.email ?? ''} disabled readOnly />
      <FormField id="full_name" label="Full name" autoComplete="name" value={fullName} error={errors.fullName} onChange={(e) => setFullName(e.target.value)} />
      <FormField id="current_password" label="Current password (required to change password)" type="password" autoComplete="current-password" value={currentPassword} error={errors.currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
      <FormField id="password" label="New password (optional)" type="password" autoComplete="new-password" value={password} error={errors.password} onChange={(e) => setPassword(e.target.value)} />
      <GradientButton type="submit" disabled={submitting}>
        {submitting ? 'Saving...' : 'Save changes'}
      </GradientButton>
    </form>
  )
}
