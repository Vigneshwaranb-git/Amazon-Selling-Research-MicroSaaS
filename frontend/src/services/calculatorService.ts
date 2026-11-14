import api from '@/services/api'
import type {
  CalculationResult,
  CostInputs,
  Scenario,
  ScenarioPayload,
  SimulateRequest,
  SimulateResponse,
} from '@/types/calculator'

/** Backend response shapes: percentages arrive as `margin_pct` / `roi_pct` and may be null. */
interface ApiCalculation {
  selling_price: string
  total_cost: string
  net_profit: string
  margin_pct: string | null
  roi_pct: string | null
  break_even_price: string
}

interface ApiSimulation {
  break_even_price: string
  results: ApiCalculation[]
}

function toResult(raw: ApiCalculation): CalculationResult {
  return {
    total_cost: raw.total_cost,
    net_profit: raw.net_profit,
    margin: raw.margin_pct ?? '',
    roi: raw.roi_pct ?? '',
    break_even_price: raw.break_even_price,
  }
}

export const calculatorService = {
  async calculate(inputs: CostInputs): Promise<CalculationResult> {
    const { data } = await api.post<ApiCalculation>('/calculator/calculate', inputs)
    return toResult(data)
  },
  async simulate(req: SimulateRequest): Promise<SimulateResponse> {
    const { data } = await api.post<ApiSimulation>('/calculator/simulate', req)
    return {
      break_even_price: data.break_even_price,
      points: data.results.map((r) => ({
        selling_price: r.selling_price,
        net_profit: r.net_profit,
        margin: r.margin_pct ?? '',
        roi: r.roi_pct ?? '',
      })),
    }
  },
  async listScenarios(): Promise<Scenario[]> {
    const { data } = await api.get<Scenario[]>('/scenarios')
    return data
  },
  async getScenario(id: number): Promise<Scenario> {
    const { data } = await api.get<Scenario>(`/scenarios/${id}`)
    return data
  },
  async createScenario(payload: ScenarioPayload): Promise<Scenario> {
    const { data } = await api.post<Scenario>('/scenarios', payload)
    return data
  },
  async updateScenario(id: number, payload: ScenarioPayload): Promise<Scenario> {
    const { data } = await api.put<Scenario>(`/scenarios/${id}`, payload)
    return data
  },
  async deleteScenario(id: number): Promise<void> {
    await api.delete(`/scenarios/${id}`)
  },
}
