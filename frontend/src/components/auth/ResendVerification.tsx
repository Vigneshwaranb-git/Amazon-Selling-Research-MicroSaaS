import { useState } from 'react'
import { FormError } from '@/components/auth/FormField'
import { Button } from '@/components/ui/button'
import { getErrorMessage, getErrorStatus } from '@/lib/errors'
import { resendVerification } from '@/services/authService'

interface ResendVerificationProps {
  email: string
}

/** "Resend verification email" action with sent / rate-limited / error feedback. */
export function ResendVerification({ email }: ResendVerificationProps) {
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  const onClick = async () => {
    setSending(true)
    setError('')
    setSent(false)
    try {
      await resendVerification(email)
      setSent(true)
    } catch (err) {
      setError(
        getErrorStatus(err) === 429
          ? 'Too many requests. Please wait a few minutes before trying again.'
          : getErrorMessage(err, 'Could not send the email. Please try again.'),
      )
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="space-y-2">
      {error && <FormError message={error} />}
      {sent && (
        <p role="status" className="text-sm">
          If that account needs verifying, a new email is on its way.
        </p>
      )}
      <Button type="button" variant="outline" onClick={onClick} disabled={sending || !email}>
        {sending ? 'Sending...' : 'Resend verification email'}
      </Button>
    </div>
  )
}
