import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { GradientButton } from '@/components/ui/GradientButton'
import { FormError, FormField } from '@/components/auth/FormField'
import { validateEmail } from '@/components/auth/validation'
import { getErrorMessage } from '@/lib/errors'
import { forgotPassword } from '@/services/authService'

export function ForgotPasswordForm() {
  const [email, setEmail] = useState('')
  const [fieldError, setFieldError] = useState<string | undefined>()
  const [formError, setFormError] = useState('')
  const [done, setDone] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setFormError('')
    const err = validateEmail(email)
    setFieldError(err)
    if (err) return
    setSubmitting(true)
    try {
      await forgotPassword(email.trim())
      setDone(true)
    } catch (error) {
      setFormError(getErrorMessage(error))
    } finally {
      setSubmitting(false)
    }
  }

  if (done) {
    return (
      <div className="space-y-4 text-center" role="status">
        <p>If an account exists for that email, a reset link is on its way.</p>
        <Link to="/login" className="underline">
          Back to sign in
        </Link>
      </div>
    )
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {formError && <FormError message={formError} />}
      <FormField id="email" label="Email" type="email" autoComplete="email" value={email} error={fieldError} onChange={(e) => setEmail(e.target.value)} />
      <GradientButton type="submit" disabled={submitting} className="w-full">
        {submitting ? 'Please wait...' : 'Send reset link'}
      </GradientButton>
      <p className="text-center text-sm">
        <Link to="/login" className="underline">
          Back to sign in
        </Link>
      </p>
    </form>
  )
}
