import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '@/services/api'
import { calculatorService } from '@/services/calculatorService'
import { EMPTY_INPUTS } from '@/lib/fees'
import type { ScenarioPayload, SimulateRequest } from '@/types/calculator'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))
const mocked = vi.mocked(api)

beforeEach(() => {
  mocked.get.mockReset()
  mocked.post.mockReset()
  mocked.put.mockReset()
  mocked.delete.mockReset()
})

const apiCalc = {
  selling_price: '20.00',
  total_cost: '18.00',
  net_profit: '2.00',
  margin_pct: '10.00',
  roi_pct: '21.05',
  break_even_price: '18.00',
}

describe('calculate', () => {
  it('maps margin_pct/roi_pct to margin/roi', async () => {
    mocked.post.mockResolvedValue({ data: apiCalc })
    const r = await calculatorService.calculate(EMPTY_INPUTS)
    expect(mocked.post).toHaveBeenCalledWith('/calculator/calculate', EMPTY_INPUTS)
    expect(r).toEqual({
      total_cost: '18.00',
      net_profit: '2.00',
      margin: '10.00',
      roi: '21.05',
      break_even_price: '18.00',
    })
    expect(r).not.toHaveProperty('margin_pct')
  })
  it('turns null percentages into empty strings', async () => {
    mocked.post.mockResolvedValue({ data: { ...apiCalc, margin_pct: null, roi_pct: null } })
    const r = await calculatorService.calculate(EMPTY_INPUTS)
    expect(r.margin).toBe('')
    expect(r.roi).toBe('')
  })
})

describe('simulate', () => {
  it('maps results to points and keeps break_even_price', async () => {
    mocked.post.mockResolvedValue({
      data: {
        break_even_price: '18.00',
        results: [apiCalc, { ...apiCalc, selling_price: '25.00', margin_pct: null, roi_pct: null }],
      },
    })
    const req = { ...EMPTY_INPUTS, prices: ['20.00', '25.00'] } as unknown as SimulateRequest
    const r = await calculatorService.simulate(req)
    expect(mocked.post).toHaveBeenCalledWith('/calculator/simulate', req)
    expect(r.break_even_price).toBe('18.00')
    expect(r.points).toEqual([
      { selling_price: '20.00', net_profit: '2.00', margin: '10.00', roi: '21.05' },
      { selling_price: '25.00', net_profit: '2.00', margin: '', roi: '' },
    ])
  })
  it('handles an empty result set', async () => {
    mocked.post.mockResolvedValue({ data: { break_even_price: '1.00', results: [] } })
    const r = await calculatorService.simulate({} as unknown as SimulateRequest)
    expect(r.points).toEqual([])
  })
})

describe('scenario CRUD', () => {
  const payload = { name: 'x' } as unknown as ScenarioPayload
  it('uses the right verbs and returns data', async () => {
    mocked.get.mockResolvedValue({ data: [{ id: 1 }] })
    expect(await calculatorService.listScenarios()).toEqual([{ id: 1 }])
    expect(mocked.get).toHaveBeenCalledWith('/scenarios')
    mocked.get.mockResolvedValue({ data: { id: 5 } })
    expect(await calculatorService.getScenario(5)).toEqual({ id: 5 })
    expect(mocked.get).toHaveBeenLastCalledWith('/scenarios/5')
    mocked.post.mockResolvedValue({ data: { id: 6 } })
    expect(await calculatorService.createScenario(payload)).toEqual({ id: 6 })
    expect(mocked.post).toHaveBeenCalledWith('/scenarios', payload)
    mocked.put.mockResolvedValue({ data: { id: 6 } })
    await calculatorService.updateScenario(6, payload)
    expect(mocked.put).toHaveBeenCalledWith('/scenarios/6', payload)
    await calculatorService.deleteScenario(6)
    expect(mocked.delete).toHaveBeenCalledWith('/scenarios/6')
  })
})
