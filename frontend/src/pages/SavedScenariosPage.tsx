import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Button } from '@/components/ui/button'
import { ScenarioCard } from '@/components/calculator/ScenarioCard'
import { ScenarioTable } from '@/components/calculator/ScenarioTable'
import { getErrorMessage } from '@/lib/errors'
import { calculatorService } from '@/services/calculatorService'
import type { Scenario } from '@/types/calculator'

export default function SavedScenariosPage() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    calculatorService
      .listScenarios()
      .then((data) => {
        if (active) setScenarios(data)
      })
      .catch((err: unknown) => {
        if (active) setError(getErrorMessage(err, 'Could not load scenarios.'))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const handleDelete = useCallback(async (id: number) => {
    try {
      await calculatorService.deleteScenario(id)
      setScenarios((prev) => prev.filter((s) => s.id !== id))
    } catch (err) {
      setError(getErrorMessage(err, 'Could not delete scenario.'))
    }
  }, [])

  const onDelete = (id: number) => {
    void handleDelete(id)
  }

  return (
    <PageWrapper>
      <main className="mx-auto flex max-w-6xl flex-col gap-6 p-4 sm:p-8">
        <header className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-2xl font-bold">Saved Scenarios</h1>
          <Button asChild>
            <Link to="/calculator">New calculation</Link>
          </Button>
        </header>

        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
        {loading && <p className="text-muted-foreground">Loading...</p>}
        {!loading && scenarios.length === 0 && !error && (
          <p className="text-muted-foreground">No saved scenarios yet. Save one from the calculator.</p>
        )}

        {scenarios.length > 0 && (
          <>
            <div className="hidden md:block">
              <ScenarioTable scenarios={scenarios} onDelete={onDelete} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2 md:hidden">
              <AnimatePresence>
                {scenarios.map((s) => (
                  <ScenarioCard key={s.id} scenario={s} onDelete={onDelete} />
                ))}
              </AnimatePresence>
            </div>
          </>
        )}
      </main>
    </PageWrapper>
  )
}
