import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { GradientButton } from '@/components/ui/GradientButton'
import { FormError, FormField } from '@/components/auth/FormField'
import { validatePassword } from '@/components/auth/validation'
import { getErrorMessage } from '@/lib/errors'
import { resetPassword } from '@/services/authService'

export function ResetPasswordForm({ token }: { token: string }) {
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [passwordError, setPasswordError] = useState<string | undefined>()
  const [confirmError, setConfirmError] = useState<string | undefined>()
  const [formError, setFormError] = useState('')
  const [done, setDone] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setFormError('')
    const pwErr = validatePassword(password)
    const confirmErr = confirm !== password ? 'Passwords do not match' : undefined
    setPasswordError(pwErr)
    setConfirmError(confirmErr)
    if (pwErr || confirmErr) return
    setSubmitting(true)
    try {
      await resetPassword(token, password)
      setDone(true)
    } catch (error) {
      setFormError(getErrorMessage(error, 'Could not reset your password. The link may have expired.'))
    } finally {
      setSubmitting(false)
    }
  }

  if (done) {
    return (
      <div className="space-y-4 text-center" role="status">
        <p>Your password has been reset. You can now sign in.</p>
        <Link to="/login" className="underline">
          Back to sign in
        </Link>
      </div>
    )
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {formError && <FormError message={formError} />}
      <FormField id="new_password" label="New password" type="password" autoComplete="new-password" value={password} error={passwordError} onChange={(e) => setPassword(e.target.value)} />
      <FormField id="confirm" label="Confirm password" type="password" autoComplete="new-password" value={confirm} error={confirmError} onChange={(e) => setConfirm(e.target.value)} />
      <GradientButton type="submit" disabled={submitting} className="w-full">
        {submitting ? 'Please wait...' : 'Reset password'}
      </GradientButton>
    </form>
  )
}
