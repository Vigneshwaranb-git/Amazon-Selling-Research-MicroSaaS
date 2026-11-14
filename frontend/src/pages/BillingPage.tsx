import { PageWrapper } from '@/components/layout/PageWrapper'
import { SubscriptionStatus } from '@/components/billing/SubscriptionStatus'
import { Button } from '@/components/ui/button'
import { useSubscription } from '@/hooks/useSubscription'

export default function BillingPage() {
  const { subscription, loading, error, refetch } = useSubscription()
  return (
    <PageWrapper>
      <main className="mx-auto max-w-2xl space-y-4 p-8">
        <h1 className="text-2xl font-bold">Billing</h1>
        {loading && !subscription && <p className="text-muted-foreground">Loading subscription...</p>}
        {error && (
          <div role="alert" className="space-y-2">
            <p className="text-destructive">{error}</p>
            <Button variant="outline" onClick={() => void refetch()}>
              Retry
            </Button>
          </div>
        )}
        {subscription && <SubscriptionStatus subscription={subscription} />}
      </main>
    </PageWrapper>
  )
}
