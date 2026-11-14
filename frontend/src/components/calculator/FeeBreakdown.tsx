import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { formatMoney, formatPercent, toCents } from '@/lib/fees'
import type { CalculationResult, CostInputs } from '@/types/calculator'

interface FeeBreakdownProps {
  inputs: CostInputs
  result: CalculationResult
  mismatch?: boolean
}

const LINES: { key: keyof CostInputs; label: string }[] = [
  { key: 'unit_cost', label: 'Unit cost' },
  { key: 'shipping_cost', label: 'Shipping' },
  { key: 'referral_fee', label: 'Referral fee' },
  { key: 'fba_fulfillment_fee', label: 'FBA fee' },
  { key: 'storage_fee', label: 'Storage' },
  { key: 'vat_tax', label: 'VAT / tax' },
]

export function FeeBreakdown({ inputs, result, mismatch = false }: FeeBreakdownProps) {
  const profitable = toCents(result.net_profit) >= 0
  return (
    <Card>
      <CardHeader>
        <CardTitle>Breakdown</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <dl className="flex flex-col gap-1 text-sm">
          <div className="flex justify-between">
            <dt>Selling price</dt>
            <dd className="font-medium">{formatMoney(inputs.selling_price)}</dd>
          </div>
          {LINES.map((l) => (
            <div key={l.key} className="flex justify-between text-muted-foreground">
              <dt>- {l.label}</dt>
              <dd>{formatMoney(inputs[l.key])}</dd>
            </div>
          ))}
          <div className="flex justify-between border-t pt-1 font-medium">
            <dt>Total costs</dt>
            <dd>{formatMoney(result.total_cost)}</dd>
          </div>
        </dl>

        <motion.div
          key={result.net_profit}
          initial={{ scale: 0.97, opacity: 0.6 }}
          animate={{ scale: 1, opacity: 1 }}
          className={cn(
            'rounded-lg p-4 text-center',
            profitable ? 'bg-green-500/10 text-green-600' : 'bg-red-500/10 text-red-600',
          )}
        >
          <p className="text-xs uppercase tracking-wide">Net profit per unit</p>
          <p className="text-3xl font-bold" data-testid="net-profit">
            {formatMoney(result.net_profit)}
          </p>
        </motion.div>

        <div className="grid grid-cols-3 gap-2 text-center text-sm">
          <div>
            <p className="text-muted-foreground">Margin</p>
            <p className="font-semibold">{formatPercent(result.margin)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">ROI</p>
            <p className="font-semibold">{formatPercent(result.roi)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Break-even</p>
            <p className="font-semibold">{formatMoney(result.break_even_price)}</p>
          </div>
        </div>

        {mismatch && (
          <p role="alert" className="text-xs text-amber-600">
            Server calculation differs from this estimate. Server values are authoritative when saved.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
