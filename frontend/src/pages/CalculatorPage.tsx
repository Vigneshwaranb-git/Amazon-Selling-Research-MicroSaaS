import { Link } from 'react-router-dom'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { CostForm } from '@/components/calculator/CostForm'
import { FeeBreakdown } from '@/components/calculator/FeeBreakdown'
import { PriceSimulator } from '@/components/calculator/PriceSimulator'
import { useCalculator } from '@/hooks/useCalculator'

export default function CalculatorPage() {
  const calc = useCalculator()

  return (
    <PageWrapper>
      <main className="mx-auto flex max-w-6xl flex-col gap-6 p-4 sm:p-8">
        <header className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-2xl font-bold">Profit Calculator</h1>
          <Button asChild variant="outline">
            <Link to="/calculator/saved">Saved scenarios</Link>
          </Button>
        </header>

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="flex flex-col gap-6">
            <CostForm inputs={calc.inputs} onChange={calc.setField} asin={calc.asin} onAsinChange={calc.setAsin} />
            <Card>
              <CardContent className="flex flex-col gap-3">
                <label className="flex flex-col gap-1 text-sm font-medium">
                  Scenario name
                  <Input
                    value={calc.name}
                    maxLength={150}
                    onChange={(e) => calc.setName(e.target.value)}
                    placeholder="e.g. Bamboo cutting board - base case"
                  />
                </label>
                <div className="flex gap-2">
                  <Button onClick={() => void calc.save()} disabled={calc.saving}>
                    {calc.saving ? 'Saving...' : 'Save scenario'}
                  </Button>
                  <Button variant="outline" onClick={calc.reset}>
                    Reset
                  </Button>
                </div>
                {calc.error && (
                  <p role="alert" className="text-sm text-red-600">
                    {calc.error}
                  </p>
                )}
                {calc.saved && (
                  <p role="status" className="text-sm text-green-600">
                    Saved "{calc.saved.name}".
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
          <div className="flex flex-col gap-6">
            <FeeBreakdown inputs={calc.inputs} result={calc.result} mismatch={calc.mismatch} />
            <PriceSimulator inputs={calc.inputs} />
          </div>
        </div>
      </main>
    </PageWrapper>
  )
}
