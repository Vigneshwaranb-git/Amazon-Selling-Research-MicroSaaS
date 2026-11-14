import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { getErrorMessage } from '@/lib/errors'
import { downloadBlob } from '@/lib/files'
import { exportProductsCsv } from '@/services/productService'
import type { ProductFilters } from '@/types/products'

function exportFilename(date: Date = new Date()): string {
  return `amzscoutiq-products-${date.toISOString().slice(0, 10)}.csv`
}

export function ExportCsvButton({ filters }: { filters: ProductFilters }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onClick = async () => {
    setBusy(true)
    setError(null)
    try {
      downloadBlob(await exportProductsCsv(filters), exportFilename())
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Could not export products. Please try again.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex items-center gap-3">
      <Button type="button" variant="outline" disabled={busy} onClick={() => void onClick()}>
        {busy ? 'Exporting...' : 'Export CSV'}
      </Button>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}
