import type { ChangeEvent } from 'react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { fromCents, isValidMoney, toCents } from '@/lib/fees'
import type { CostInputs } from '@/types/calculator'

interface FieldDef {
  key: keyof CostInputs
  label: string
}

const FIELDS: FieldDef[] = [
  { key: 'selling_price', label: 'Selling price' },
  { key: 'unit_cost', label: 'Unit cost (COGS)' },
  { key: 'shipping_cost', label: 'Inbound shipping' },
  { key: 'referral_fee', label: 'Referral fee' },
  { key: 'fba_fulfillment_fee', label: 'FBA fulfillment fee' },
  { key: 'storage_fee', label: 'Storage fee' },
  { key: 'vat_tax', label: 'VAT / tax' },
]

const DEFAULT_REFERRAL_PCT = 15

interface CostFormProps {
  inputs: CostInputs
  onChange: (field: keyof CostInputs, value: string) => void
  asin: string
  onAsinChange: (value: string) => void
}

export function CostForm({ inputs, onChange, asin, onAsinChange }: CostFormProps) {
  const handle = (key: keyof CostInputs) => (e: ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value
    if (isValidMoney(v)) onChange(key, v)
  }

  const applyReferralPct = () => {
    const cents = Math.round((toCents(inputs.selling_price) * DEFAULT_REFERRAL_PCT) / 100)
    onChange('referral_fee', fromCents(cents))
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Costs and fees</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-2">
        {FIELDS.map((f) => (
          <label key={f.key} className="flex flex-col gap-1 text-sm font-medium">
            {f.label}
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">$</span>
              <Input
                inputMode="decimal"
                placeholder="0.00"
                value={inputs[f.key]}
                onChange={handle(f.key)}
                aria-label={f.label}
              />
            </div>
            {f.key === 'referral_fee' && (
              <Button type="button" variant="link" size="sm" className="h-auto justify-start p-0" onClick={applyReferralPct}>
                Use {DEFAULT_REFERRAL_PCT}% of price
              </Button>
            )}
          </label>
        ))}
        <label className="flex flex-col gap-1 text-sm font-medium sm:col-span-2">
          Link to ASIN (optional)
          <Input
            placeholder="B0XXXXXXXX"
            maxLength={10}
            value={asin}
            onChange={(e) => onAsinChange(e.target.value)}
            aria-label="ASIN"
          />
        </label>
      </CardContent>
    </Card>
  )
}
