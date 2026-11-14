import { useState } from 'react'
import { CsvDropzone } from '@/components/settings/CsvDropzone'
import { ImportErrorList } from '@/components/settings/ImportErrorList'
import { Button } from '@/components/ui/button'
import { getErrorMessage } from '@/lib/errors'
import { downloadBlob, validateCsvFile } from '@/lib/files'
import { importCostSheet, type CostSheetImportResult } from '@/services/importService'

/** Client-side template. Columns are a best guess of the cost sheet contract; adjust with the backend. */
export const COST_SHEET_TEMPLATE =
  'name,asin,unit_cost,shipping_cost,referral_fee,fba_fulfillment_fee,storage_fee,vat_tax,selling_price\n' +
  'Example product,B000000000,6.50,1.20,3.75,3.22,0.15,0.00,24.99\n'

export function CostSheetImport() {
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<CostSheetImportResult | null>(null)

  const onFile = (picked: File) => {
    const invalid = validateCsvFile(picked)
    setFileError(invalid)
    setFile(invalid ? null : picked)
    setResult(null)
  }

  const onSubmit = async () => {
    if (!file) return
    setSubmitting(true)
    setError(null)
    setResult(null)
    try {
      setResult(await importCostSheet(file))
      setFile(null)
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Import failed. Please check the file and try again.'))
    } finally {
      setSubmitting(false)
    }
  }

  const onTemplate = () =>
    downloadBlob(new Blob([COST_SHEET_TEMPLATE], { type: 'text/csv' }), 'cost-sheet-template.csv')

  return (
    <div className="space-y-3">
      <h3 className="font-medium">Import a cost sheet</h3>
      <p className="text-sm text-muted-foreground">
        Bulk-create calculator scenarios from a CSV.{' '}
        <button type="button" className="underline" onClick={onTemplate}>
          Download template
        </button>
      </p>
      <CsvDropzone label="Cost sheet CSV file" file={file} disabled={submitting} onFile={onFile} />
      {fileError && (
        <p role="alert" className="text-sm text-destructive">
          {fileError}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <Button type="button" disabled={!file || submitting} onClick={() => void onSubmit()}>
        {submitting ? 'Importing...' : 'Import cost sheet'}
      </Button>
      {result && (
        <div role="status" className="space-y-2 text-sm">
          <p>Created {result.created} scenario(s).</p>
          <ImportErrorList errors={result.errors} />
        </div>
      )}
    </div>
  )
}
