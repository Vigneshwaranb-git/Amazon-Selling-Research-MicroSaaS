import { describe, expect, it } from 'vitest'
import {
  EMPTY_INPUTS,
  calculate,
  formatMoney,
  formatPercent,
  fromCents,
  isValidMoney,
  priceLadder,
  simulatePrices,
  toCents,
  totalCostCents,
} from '@/lib/fees'
import type { CostInputs } from '@/types/calculator'

const base: CostInputs = {
  unit_cost: '8.00',
  shipping_cost: '1.50',
  referral_fee: '3.00',
  fba_fulfillment_fee: '4.25',
  storage_fee: '0.30',
  vat_tax: '0.95',
  selling_price: '20.00',
}

describe('toCents edge cases', () => {
  it('handles whitespace, leading/trailing dots and rounding', () => {
    expect(toCents('  12.34  ')).toBe(1234)
    expect(toCents('.5')).toBe(50)
    expect(toCents('5.')).toBe(500)
    expect(toCents('0.004')).toBe(0)
    expect(toCents('0.005')).toBe(1)
    expect(toCents('0.999')).toBe(100)
    expect(toCents('-0.005')).toBe(-1)
    expect(toCents('007')).toBe(700)
  })
  it('rejects non-decimal formats as 0', () => {
    for (const bad of ['1e3', '1,000', '$5', '--1', '+5', '1.2.3', 'Infinity', 'NaN', '-']) {
      expect(toCents(bad)).toBe(0)
    }
  })
  it('stays exact for large amounts', () => {
    expect(toCents('99999999.99')).toBe(9999999999)
  })
})

describe('fromCents edge cases', () => {
  it('formats zero, negatives under a dollar, and large values', () => {
    expect(fromCents(0)).toBe('0.00')
    expect(fromCents(-5)).toBe('-0.05')
    expect(fromCents(100)).toBe('1.00')
    expect(fromCents(9999999999)).toBe('99999999.99')
  })
  it('round-trips through toCents', () => {
    for (const c of [0, 1, 99, 100, 12345, -1, -9999]) expect(toCents(fromCents(c))).toBe(c)
  })
})

describe('calculate edge cases', () => {
  it('returns zeros for fully empty inputs', () => {
    expect(calculate(EMPTY_INPUTS)).toEqual({
      total_cost: '0.00',
      net_profit: '0.00',
      margin: '0.00',
      roi: '0.00',
      break_even_price: '0.00',
    })
  })
  it('computes negative margin and roi for a deep loss', () => {
    const r = calculate({ ...base, selling_price: '9.00' })
    expect(r.net_profit).toBe('-9.00')
    expect(r.margin).toBe('-100.00')
    expect(r.roi).toBe('-94.74')
  })
  it('rounds percentages to 2 decimals', () => {
    const r = calculate({ ...EMPTY_INPUTS, unit_cost: '0.02', selling_price: '0.03' })
    expect(r.margin).toBe('33.33')
    expect(r.roi).toBe('50.00')
    const r2 = calculate({ ...EMPTY_INPUTS, unit_cost: '0.01', selling_price: '0.03' })
    expect(r2.margin).toBe('66.67')
  })
  it('reports 0.00 roi when landed cost is zero', () => {
    const r = calculate({ ...EMPTY_INPUTS, selling_price: '10', referral_fee: '1' })
    expect(r.roi).toBe('0.00')
    expect(r.margin).toBe('90.00')
  })
  it('totals all six cost fields', () => {
    expect(totalCostCents(base)).toBe(1800)
  })
})

describe('simulatePrices edge cases', () => {
  it('keeps referral fixed when the base price is 0', () => {
    const [p] = simulatePrices({ ...base, selling_price: '0' }, ['20.00'])
    expect(p.net_profit).toBe('2.00')
  })
  it('returns [] for no prices and normalises price strings', () => {
    expect(simulatePrices(base, [])).toEqual([])
    expect(simulatePrices(base, ['20'])[0].selling_price).toBe('20.00')
  })
  it('equals calculate() at the base price', () => {
    const [p] = simulatePrices(base, ['20.00'])
    const r = calculate(base)
    expect([p.net_profit, p.margin, p.roi]).toEqual([r.net_profit, r.margin, r.roi])
  })
})

describe('priceLadder edge cases', () => {
  it('clamps negative results to 0.00 and handles empty input', () => {
    expect(priceLadder('10.00', [-150])).toEqual(['0.00'])
    expect(priceLadder('10.00', [])).toEqual([])
    expect(priceLadder('', [10])).toEqual(['0.00'])
  })
})

describe('formatters and validators', () => {
  it('formatMoney handles zero, invalid and rounding', () => {
    expect(formatMoney('')).toBe('$0.00')
    expect(formatMoney('abc')).toBe('$0.00')
    expect(formatMoney('-0.05')).toBe('-$0.05')
    expect(formatMoney('999.999')).toBe('$1,000.00')
  })
  it('formatPercent', () => {
    expect(formatPercent(null)).toBe('-')
    expect(formatPercent('12.50')).toBe('12.50%')
  })
  it('isValidMoney', () => {
    for (const ok of ['', '0', '12', '12.', '12.3', '12.34']) expect(isValidMoney(ok)).toBe(true)
    for (const bad of ['-1', '12.345', '.5', 'a', '1,0', ' 1']) expect(isValidMoney(bad)).toBe(false)
  })
})
