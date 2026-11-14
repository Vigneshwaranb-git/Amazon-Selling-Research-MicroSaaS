import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { GradientButton } from '@/components/ui/GradientButton'
import { FormError, FormField } from '@/components/auth/FormField'
import { validateEmail, validatePassword } from '@/components/auth/validation'
import { GoogleLoginButton } from '@/components/auth/GoogleLoginButton'
import { useAuth } from '@/hooks/useAuth'
import { getErrorMessage } from '@/lib/errors'

interface RegisterErrors {
  fullName?: string
  email?: string
  password?: string
  confirm?: string
}

export function RegisterForm() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [errors, setErrors] = useState<RegisterErrors>({})
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const next: RegisterErrors = {
      fullName: fullName.trim() ? undefined : 'Full name is required',
      email: validateEmail(email),
      password: validatePassword(password),
      confirm: confirm === password ? undefined : 'Passwords do not match',
    }
    setErrors(next)
    setFormError('')
    if (Object.values(next).some(Boolean)) return
    setSubmitting(true)
    try {
      await register({ email: email.trim(), password, full_name: fullName.trim() })
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setFormError(getErrorMessage(err, 'Registration failed. Please try again.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {formError && <FormError message={formError} />}
      <FormField id="full_name" label="Full name" autoComplete="name" value={fullName} error={errors.fullName} onChange={(e) => setFullName(e.target.value)} />
      <FormField id="email" label="Email" type="email" autoComplete="email" value={email} error={errors.email} onChange={(e) => setEmail(e.target.value)} />
      <FormField id="password" label="Password" type="password" autoComplete="new-password" value={password} error={errors.password} onChange={(e) => setPassword(e.target.value)} />
      <FormField id="confirm" label="Confirm password" type="password" autoComplete="new-password" value={confirm} error={errors.confirm} onChange={(e) => setConfirm(e.target.value)} />
      <GradientButton type="submit" disabled={submitting} className="w-full">
        {submitting ? 'Creating account...' : 'Create account'}
      </GradientButton>
      <GoogleLoginButton label="Sign up with Google" />
      <p className="text-center text-sm">
        Already have an account?{' '}
        <Link to="/login" className="underline">
          Sign in
        </Link>
      </p>
    </form>
  )
}
