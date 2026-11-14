import { Check } from 'lucide-react'
import { motion } from 'framer-motion'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { SubscriptionTier } from '@/types'

export interface PlanDefinition {
  tier: SubscriptionTier
  name: string
  priceLabel: string
  description: string
  features: string[]
  highlighted?: boolean
}

interface PlanCardProps {
  plan: PlanDefinition
  isCurrent: boolean
  loading?: boolean
  onSelect: (tier: SubscriptionTier) => void
}

export function PlanCard({ plan, isCurrent, loading = false, onSelect }: PlanCardProps) {
  const isFree = plan.tier === 'free'
  const label = isCurrent ? 'Current plan' : isFree ? 'Included' : loading ? 'Redirecting...' : `Upgrade to ${plan.name}`
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
      <Card className={cn('h-full', plan.highlighted && 'border-primary ring-1 ring-primary')}>
        <CardHeader>
          <CardTitle className="text-xl">{plan.name}</CardTitle>
          <CardDescription>{plan.description}</CardDescription>
          <p className="text-3xl font-bold">{plan.priceLabel}</p>
        </CardHeader>
        <CardContent className="flex-1">
          <ul className="space-y-2 text-sm">
            {plan.features.map((feature) => (
              <li key={feature} className="flex items-start gap-2">
                <Check className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
                <span>{feature}</span>
              </li>
            ))}
          </ul>
        </CardContent>
        <CardFooter>
          <Button
            className="w-full"
            variant={plan.highlighted ? 'default' : 'outline'}
            disabled={isCurrent || isFree || loading}
            onClick={() => onSelect(plan.tier)}
          >
            {label}
          </Button>
        </CardFooter>
      </Card>
    </motion.div>
  )
}
