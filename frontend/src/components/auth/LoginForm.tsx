import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { GradientButton } from '@/components/ui/GradientButton'
import { FormError, FormField } from '@/components/auth/FormField'
import { validateEmail } from '@/components/auth/validation'
import { GoogleLoginButton } from '@/components/auth/GoogleLoginButton'
import { useAuth } from '@/hooks/useAuth'
import { getErrorMessage } from '@/lib/errors'

interface LocationState {
  from?: string
}

export function LoginForm() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({})
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const next = { email: validateEmail(email), password: password ? undefined : 'Password is required' }
    setErrors(next)
    setFormError('')
    if (next.email || next.password) return
    setSubmitting(true)
    try {
      await login(email.trim(), password)
      const from = (location.state as LocationState | null)?.from
      navigate(from ?? '/dashboard', { replace: true })
    } catch (err) {
      setFormError(getErrorMessage(err, 'Login failed. Please try again.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {formError && <FormError message={formError} />}
      <FormField id="email" label="Email" type="email" autoComplete="email" value={email} error={errors.email} onChange={(e) => setEmail(e.target.value)} />
      <FormField id="password" label="Password" type="password" autoComplete="current-password" value={password} error={errors.password} onChange={(e) => setPassword(e.target.value)} />
      <div className="text-right text-sm">
        <Link to="/forgot-password" className="underline">
          Forgot password?
        </Link>
      </div>
      <GradientButton type="submit" disabled={submitting} className="w-full">
        {submitting ? 'Signing in...' : 'Sign in'}
      </GradientButton>
      <GoogleLoginButton />
      <p className="text-center text-sm">
        No account?{' '}
        <Link to="/register" className="underline">
          Create one
        </Link>
      </p>
    </form>
  )
}
