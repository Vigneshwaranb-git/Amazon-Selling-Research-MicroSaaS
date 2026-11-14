/** Money values are decimal strings on the wire (e.g. "12.50"). */
export interface CostInputs {
  unit_cost: string
  shipping_cost: string
  referral_fee: string
  fba_fulfillment_fee: string
  storage_fee: string
  vat_tax: string
  selling_price: string
}

export interface CalculationResult {
  total_cost: string
  net_profit: string
  margin: string
  roi: string
  break_even_price: string
}

export interface ScenarioPayload extends CostInputs {
  name: string
  asin: string | null
  target_roi: string | null
  target_margin: string | null
}

export interface Scenario extends ScenarioPayload {
  id: number
  user_id: number
  net_profit: string | null
  roi: string | null
  margin: string | null
  created_at: string
}

export interface SimulateRequest extends CostInputs {
  prices: string[]
}

export interface SimulatePoint {
  selling_price: string
  net_profit: string
  margin: string
  roi: string
}

export interface SimulateResponse {
  break_even_price: string
  points: SimulatePoint[]
}
