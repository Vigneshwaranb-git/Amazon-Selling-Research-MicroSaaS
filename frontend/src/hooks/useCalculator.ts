import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getErrorMessage } from '@/lib/errors'
import { calculate, EMPTY_INPUTS } from '@/lib/fees'
import { calculatorService } from '@/services/calculatorService'
import type { CalculationResult, CostInputs, Scenario } from '@/types/calculator'

const VALIDATE_DELAY_MS = 600

export interface UseCalculator {
  inputs: CostInputs
  setField: (field: keyof CostInputs, value: string) => void
  result: CalculationResult
  mismatch: boolean
  name: string
  setName: (v: string) => void
  asin: string
  setAsin: (v: string) => void
  saving: boolean
  error: string | null
  saved: Scenario | null
  save: () => Promise<void>
  reset: () => void
}

export function useCalculator(): UseCalculator {
  const [inputs, setInputs] = useState<CostInputs>(EMPTY_INPUTS)
  const [serverResult, setServerResult] = useState<CalculationResult | null>(null)
  const [name, setName] = useState('')
  const [asin, setAsin] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<Scenario | null>(null)
  const requestId = useRef(0)

  // Instant client-side result on every keystroke.
  const result = useMemo(() => calculate(inputs), [inputs])

  // Debounced validation against the API.
  useEffect(() => {
    if (inputs.selling_price === '') return
    const id = ++requestId.current
    const t = setTimeout(() => {
      calculatorService
        .calculate(inputs)
        .then((r) => {
          if (id === requestId.current) setServerResult(r)
        })
        .catch(() => {
          if (id === requestId.current) setServerResult(null)
        })
    }, VALIDATE_DELAY_MS)
    return () => clearTimeout(t)
  }, [inputs])

  const setField = useCallback((field: keyof CostInputs, value: string) => {
    setInputs((prev) => ({ ...prev, [field]: value }))
    setSaved(null)
  }, [])

  // Compare numerically: the API and the client format the same value differently ("33.3" vs "33.30").
  const differs = (a: string, b: string): boolean => Math.abs(Number(a) - Number(b)) > 0.005
  const mismatch =
    serverResult !== null &&
    (differs(serverResult.net_profit, result.net_profit) ||
      (serverResult.margin !== '' && differs(serverResult.margin, result.margin)))

  const save = useCallback(async () => {
    if (!name.trim()) {
      setError('Give the scenario a name.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const trimmed = asin.trim().toUpperCase()
      const created = await calculatorService.createScenario({
        ...inputs,
        name: name.trim(),
        asin: trimmed === '' ? null : trimmed,
        target_roi: null,
        target_margin: null,
      })
      setSaved(created)
    } catch (err) {
      setError(getErrorMessage(err, 'Could not save scenario.'))
    } finally {
      setSaving(false)
    }
  }, [asin, inputs, name])

  const reset = useCallback(() => {
    setInputs(EMPTY_INPUTS)
    setName('')
    setAsin('')
    setSaved(null)
    setError(null)
    setServerResult(null)
  }, [])

  return { inputs, setField, result, mismatch, name, setName, asin, setAsin, saving, error, saved, save, reset }
}
