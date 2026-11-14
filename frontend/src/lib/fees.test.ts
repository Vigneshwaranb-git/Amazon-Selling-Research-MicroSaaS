import { describe, expect, it } from 'vitest'
import { calculate, formatMoney, fromCents, priceLadder, simulatePrices, toCents } from '@/lib/fees'
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

describe('toCents / fromCents', () => {
  it('parses decimals without float drift', () => {
    expect(toCents('0.1') + toCents('0.2')).toBe(30)
    expect(toCents('19.99')).toBe(1999)
    expect(toCents('1.005')).toBe(101)
    expect(toCents('-2.50')).toBe(-250)
  })
  it('treats invalid or empty as 0', () => {
    expect(toCents('')).toBe(0)
    expect(toCents('abc')).toBe(0)
    expect(toCents('.')).toBe(0)
  })
  it('formats cents', () => {
    expect(fromCents(5)).toBe('0.05')
    expect(fromCents(-1234)).toBe('-12.34')
  })
})

describe('calculate', () => {
  it('computes net profit, margin, roi and break-even', () => {
    const r = calculate(base)
    expect(r.total_cost).toBe('18.00')
    expect(r.net_profit).toBe('2.00')
    expect(r.margin).toBe('10.00')
    expect(r.roi).toBe('21.05')
    expect(r.break_even_price).toBe('18.00')
  })
  it('handles a loss', () => {
    const r = calculate({ ...base, selling_price: '15.00' })
    expect(r.net_profit).toBe('-3.00')
    expect(r.margin).toBe('-20.00')
  })
  it('guards zero price and zero landed cost', () => {
    const r = calculate({ ...base, selling_price: '0', unit_cost: '0', shipping_cost: '0' })
    expect(r.margin).toBe('0.00')
    expect(r.roi).toBe('0.00')
  })
  it('has no drift with 0.1 + 0.2 style inputs', () => {
    const r = calculate({
      ...base,
      unit_cost: '0.10',
      shipping_cost: '0.20',
      referral_fee: '0',
      fba_fulfillment_fee: '0',
      storage_fee: '0',
      vat_tax: '0',
      selling_price: '0.30',
    })
    expect(r.net_profit).toBe('0.00')
  })
})

describe('simulatePrices', () => {
  it('scales referral fee with price', () => {
    const [p] = simulatePrices(base, ['40.00'])
    expect(p.net_profit).toBe('19.00')
  })
  it('builds a price ladder', () => {
    expect(priceLadder('20.00', [-10, 0, 10])).toEqual(['18.00', '20.00', '22.00'])
  })
})

describe('formatMoney', () => {
  it('adds separators', () => {
    expect(formatMoney('1234567.5')).toBe('$1,234,567.50')
    expect(formatMoney('-3')).toBe('-$3.00')
  })
})
