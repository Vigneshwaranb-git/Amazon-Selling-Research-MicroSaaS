import { useState } from 'react'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { MeshBackground } from '@/components/layout/MeshBackground'
import { PlanCard, type PlanDefinition } from '@/components/billing/PlanCard'
import { useSubscription } from '@/hooks/useSubscription'
import { createCheckout } from '@/services/billingService'
import type { SubscriptionTier } from '@/types'

// PLACEHOLDER pricing and features: to be confirmed by the product owner.
const PLANS: PlanDefinition[] = [
  { tier: 'free', name: 'Free', priceLabel: '$0 / mo', description: 'Try the basics.', features: ['Limited product lookups', '1 tracking list', 'Profit calculator'] },
  { tier: 'pro', name: 'Pro', priceLabel: '$29 / mo', description: 'For active sellers.', highlighted: true, features: ['Unlimited product lookups', '10 tracking lists', 'BSR history and sales estimates', 'Review analysis'] },
  { tier: 'business', name: 'Business', priceLabel: '$79 / mo', description: 'For teams and agencies.', features: ['Everything in Pro', 'Unlimited tracking lists', 'Analytics dashboard', 'Priority support'] },
]

function isHttpsUrl(value: string): boolean {
  try {
    return new URL(value).protocol === 'https:'
  } catch {
    return false
  }
}

export default function PricingPage() {
  const { subscription } = useSubscription()
  const [pending, setPending] = useState<SubscriptionTier | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSelect = async (tier: SubscriptionTier): Promise<void> => {
    if (tier === 'free') return
    setPending(tier)
    setError(null)
    try {
      const { checkout_url } = await createCheckout(tier)
      if (!isHttpsUrl(checkout_url)) throw new Error('Invalid checkout URL')
      window.location.assign(checkout_url)
    } catch {
      setError('Could not start checkout. Please sign in and try again.')
      setPending(null)
    }
  }

  return (
    <PageWrapper>
      <MeshBackground />
      <main className="mx-auto max-w-5xl p-8">
        <h1 className="text-center text-3xl font-bold">Pricing</h1>
        <p className="mt-2 text-center text-sm text-muted-foreground">Placeholder pricing, to be confirmed.</p>
        {error && (
          <p role="alert" className="mt-4 text-center text-sm text-destructive">
            {error}
          </p>
        )}
        <div className="mt-8 grid gap-6 md:grid-cols-3">
          {PLANS.map((plan) => (
            <PlanCard
              key={plan.tier}
              plan={plan}
              isCurrent={subscription?.plan === plan.tier}
              loading={pending === plan.tier}
              onSelect={(tier) => void handleSelect(tier)}
            />
          ))}
        </div>
      </main>
    </PageWrapper>
  )
}
