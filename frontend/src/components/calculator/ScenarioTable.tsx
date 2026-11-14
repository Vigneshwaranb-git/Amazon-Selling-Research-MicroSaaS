import { Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { formatMoney, formatPercent, toCents } from '@/lib/fees'
import type { Scenario } from '@/types/calculator'

interface ScenarioTableProps {
  scenarios: Scenario[]
  onDelete: (id: number) => void
}

export function ScenarioTable({ scenarios, onDelete }: ScenarioTableProps) {
  return (
    <div className="overflow-x-auto rounded-xl border">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 text-left text-muted-foreground">
          <tr>
            <th className="p-3 font-medium">Name</th>
            <th className="p-3 font-medium">ASIN</th>
            <th className="p-3 font-medium">Price</th>
            <th className="p-3 font-medium">Net profit</th>
            <th className="p-3 font-medium">Margin</th>
            <th className="p-3 font-medium">ROI</th>
            <th className="p-3 font-medium">Saved</th>
            <th className="p-3" />
          </tr>
        </thead>
        <tbody>
          {scenarios.map((s) => {
            const net = s.net_profit ?? '0'
            return (
              <tr key={s.id} className="border-t">
                <td className="p-3 font-medium">{s.name}</td>
                <td className="p-3">{s.asin ?? '-'}</td>
                <td className="p-3">{formatMoney(s.selling_price)}</td>
                <td className={cn('p-3', toCents(net) < 0 ? 'text-red-600' : 'text-green-600')}>{formatMoney(net)}</td>
                <td className="p-3">{formatPercent(s.margin)}</td>
                <td className="p-3">{formatPercent(s.roi)}</td>
                <td className="p-3">{new Date(s.created_at).toLocaleDateString()}</td>
                <td className="p-3 text-right">
                  <Button variant="ghost" size="icon" aria-label={`Delete ${s.name}`} onClick={() => onDelete(s.id)}>
                    <Trash2 className="size-4" />
                  </Button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
