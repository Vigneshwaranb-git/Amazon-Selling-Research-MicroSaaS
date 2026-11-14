import { motion } from 'framer-motion'
import { Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { formatMoney, formatPercent, toCents } from '@/lib/fees'
import type { Scenario } from '@/types/calculator'

interface ScenarioCardProps {
  scenario: Scenario
  onDelete: (id: number) => void
}

export function ScenarioCard({ scenario, onDelete }: ScenarioCardProps) {
  const net = scenario.net_profit ?? '0'
  return (
    <motion.div layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-2">
            <span className="truncate">{scenario.name}</span>
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Delete ${scenario.name}`}
              onClick={() => onDelete(scenario.id)}
            >
              <Trash2 className="size-4" />
            </Button>
          </CardTitle>
          {scenario.asin && <p className="text-xs text-muted-foreground">ASIN {scenario.asin}</p>}
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-2 text-sm">
          <div>
            <p className="text-muted-foreground">Price</p>
            <p className="font-medium">{formatMoney(scenario.selling_price)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Net profit</p>
            <p className={cn('font-medium', toCents(net) < 0 ? 'text-red-600' : 'text-green-600')}>
              {formatMoney(net)}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Margin</p>
            <p className="font-medium">{formatPercent(scenario.margin)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">ROI</p>
            <p className="font-medium">{formatPercent(scenario.roi)}</p>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}
