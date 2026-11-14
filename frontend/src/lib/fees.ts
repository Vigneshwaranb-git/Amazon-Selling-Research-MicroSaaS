import type { CalculationResult, CostInputs, SimulatePoint } from '@/types/calculator'

/**
 * Client-side mirror of the backend calculator. All money is handled as
 * integer cents to avoid floating point drift; percentages are rounded to
 * 2 decimals using integer arithmetic.
 */

export const EMPTY_INPUTS: CostInputs = {
  unit_cost: '',
  shipping_cost: '',
  referral_fee: '',
  fba_fulfillment_fee: '',
  storage_fee: '',
  vat_tax: '',
  selling_price: '',
}

/** Parse a decimal string into integer cents (half away from zero). Invalid -> 0. */
export function toCents(value: string): number {
  const m = /^(-?)(\d*)(?:\.(\d*))?$/.exec(value.trim())
  if (!m || (m[2] === '' && (m[3] ?? '') === '')) return 0
  const sign = m[1] === '-' ? -1 : 1
  const whole = Number(m[2] || '0')
  const frac = (m[3] ?? '').padEnd(3, '0')
  const cents = whole * 100 + Number(frac.slice(0, 2))
  const roundUp = Number(frac[2]) >= 5 ? 1 : 0
  return sign * (cents + roundUp)
}

export function fromCents(cents: number): string {
  const sign = cents < 0 ? '-' : ''
  const abs = Math.abs(cents)
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`
}

/** numerator / denominator * 100 as a 2-decimal string using integer math. */
function percent(numerator: number, denominator: number): string {
  if (denominator === 0) return '0.00'
  const sign = numerator < 0 !== denominator < 0 ? -1 : 1
  const n = Math.abs(numerator)
  const d = Math.abs(denominator)
  const hundredths = Math.floor((n * 20000 + d) / (2 * d))
  return fromCents(sign * hundredths)
}

export function totalCostCents(i: CostInputs): number {
  return (
    toCents(i.unit_cost) +
    toCents(i.shipping_cost) +
    toCents(i.referral_fee) +
    toCents(i.fba_fulfillment_fee) +
    toCents(i.storage_fee) +
    toCents(i.vat_tax)
  )
}

export function calculate(i: CostInputs): CalculationResult {
  const price = toCents(i.selling_price)
  const total = totalCostCents(i)
  const net = price - total
  const landed = toCents(i.unit_cost) + toCents(i.shipping_cost)
  return {
    total_cost: fromCents(total),
    net_profit: fromCents(net),
    margin: percent(net, price),
    roi: percent(net, landed),
    break_even_price: fromCents(total),
  }
}

/**
 * Simulate alternative prices. The referral fee is treated as a percentage of
 * the base selling price and scales with the simulated price; other fees stay fixed.
 */
export function simulatePrices(i: CostInputs, prices: string[]): SimulatePoint[] {
  const basePrice = toCents(i.selling_price)
  const referral = toCents(i.referral_fee)
  return prices.map((p) => {
    const priceCents = toCents(p)
    const scaled = basePrice > 0 ? Math.round((referral * priceCents) / basePrice) : referral
    const r = calculate({ ...i, selling_price: p, referral_fee: fromCents(scaled) })
    return { selling_price: fromCents(priceCents), net_profit: r.net_profit, margin: r.margin, roi: r.roi }
  })
}

/** Build a ladder of prices around the base price (percent offsets). */
export function priceLadder(basePrice: string, offsetsPct: number[]): string[] {
  const base = toCents(basePrice)
  return offsetsPct.map((o) => fromCents(Math.max(0, Math.round((base * (100 + o)) / 100))))
}

export function formatMoney(value: string): string {
  const cents = toCents(value)
  const sign = cents < 0 ? '-' : ''
  const abs = Math.abs(cents)
  const whole = Math.floor(abs / 100)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return `${sign}$${whole}.${String(abs % 100).padStart(2, '0')}`
}

export function formatPercent(value: string | null): string {
  return value === null ? '-' : `${value}%`
}

export function isValidMoney(value: string): boolean {
  return value === '' || /^\d+(\.\d{0,2})?$/.test(value)
}
