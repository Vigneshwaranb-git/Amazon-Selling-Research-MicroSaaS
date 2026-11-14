import { useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { formatMoney, formatPercent, priceLadder, simulatePrices, toCents } from '@/lib/fees'
import type { CostInputs } from '@/types/calculator'

const OFFSETS = [-20, -10, -5, 0, 5, 10, 20]

export function PriceSimulator({ inputs }: { inputs: CostInputs }) {
  const rows = useMemo(() => {
    if (toCents(inputs.selling_price) <= 0) return []
    return simulatePrices(inputs, priceLadder(inputs.selling_price, OFFSETS))
  }, [inputs])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Price simulator</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">Enter a selling price to compare price strategies.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="py-1 pr-2 font-medium">Change</th>
                  <th className="py-1 pr-2 font-medium">Price</th>
                  <th className="py-1 pr-2 font-medium">Net profit</th>
                  <th className="py-1 pr-2 font-medium">Margin</th>
                  <th className="py-1 font-medium">ROI</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, idx) => (
                  <tr key={OFFSETS[idx]} className={cn('border-t', OFFSETS[idx] === 0 && 'font-semibold')}>
                    <td className="py-1 pr-2">{OFFSETS[idx] > 0 ? `+${OFFSETS[idx]}` : OFFSETS[idx]}%</td>
                    <td className="py-1 pr-2">{formatMoney(r.selling_price)}</td>
                    <td className={cn('py-1 pr-2', toCents(r.net_profit) < 0 ? 'text-red-600' : 'text-green-600')}>
                      {formatMoney(r.net_profit)}
                    </td>
                    <td className="py-1 pr-2">{formatPercent(r.margin)}</td>
                    <td className="py-1">{formatPercent(r.roi)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
