import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { SubscriptionInfo } from '@/services/billingService'

interface SubscriptionStatusProps {
  subscription: SubscriptionInfo
}

const STATUS_LABELS: Record<SubscriptionInfo['status'], string> = {
  active: 'Active',
  trialing: 'Trialing',
  past_due: 'Past due',
  canceled: 'Canceled',
  inactive: 'Inactive',
}

function formatPeriodEnd(value: string | null): string {
  if (!value) return 'N/A'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'N/A'
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' })
}

export function SubscriptionStatus({ subscription }: SubscriptionStatusProps) {
  const { plan, status, current_period_end } = subscription
  const isFree = plan === 'free'
  const renewalLabel = status === 'canceled' ? 'Access ends' : 'Renews on'
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl capitalize">{plan} plan</CardTitle>
        <CardDescription>
          Status: <span data-testid="subscription-status">{STATUS_LABELS[status]}</span>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!isFree && (
          <p className="text-sm">
            {renewalLabel}: <span data-testid="period-end">{formatPeriodEnd(current_period_end)}</span>
          </p>
        )}
        {status === 'past_due' && (
          <p role="alert" className="text-sm text-destructive">
            Your last payment failed. Please update your payment method.
          </p>
        )}
        {(isFree || status === 'canceled') && (
          <Button asChild>
            <Link to="/pricing">Upgrade plan</Link>
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
