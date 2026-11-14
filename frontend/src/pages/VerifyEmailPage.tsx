import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AuthPageLayout } from '@/components/auth/AuthPageLayout'
import { FormError, FormField } from '@/components/auth/FormField'
import { ResendVerification } from '@/components/auth/ResendVerification'
import { validateEmail } from '@/components/auth/validation'
import { getErrorMessage } from '@/lib/errors'
import { verifyEmail } from '@/services/authService'

type Status = 'loading' | 'success' | 'error'

export default function VerifyEmailPage() {
  const [params] = useSearchParams()
  const token = params.get('token')
  const [status, setStatus] = useState<Status>(token ? 'loading' : 'error')
  const [message, setMessage] = useState(token ? '' : 'This verification link is invalid or incomplete.')
  const [email, setEmail] = useState('')
  const submitted = useRef(false)

  useEffect(() => {
    // Tokens are single use: submit exactly once even under React StrictMode.
    if (!token || submitted.current) return
    submitted.current = true
    verifyEmail(token)
      .then(() => setStatus('success'))
      .catch((err: unknown) => {
        setMessage(getErrorMessage(err, 'This verification link is invalid or has expired.'))
        setStatus('error')
      })
  }, [token])

  return (
    <AuthPageLayout title="Verify your email" subtitle="Confirming your email address">
      {status === 'loading' && <p role="status">Verifying your email...</p>}
      {status === 'success' && (
        <div className="space-y-4 text-center" role="status">
          <p>Your email is verified. You can now sign in.</p>
          <Link to="/login" className="underline">
            Go to sign in
          </Link>
        </div>
      )}
      {status === 'error' && (
        <div className="space-y-4">
          <FormError message={message} />
          <p className="text-sm">Enter your email to get a new verification link.</p>
          <FormField id="email" label="Email" type="email" autoComplete="email" value={email} error={email ? validateEmail(email) : undefined} onChange={(e) => setEmail(e.target.value)} />
          <ResendVerification email={validateEmail(email) ? '' : email.trim()} />
          <p className="text-center text-sm">
            <Link to="/login" className="underline">
              Back to sign in
            </Link>
          </p>
        </div>
      )}
    </AuthPageLayout>
  )
}
