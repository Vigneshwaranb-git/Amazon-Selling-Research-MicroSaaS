import { useState } from 'react'
import { CsvDropzone } from '@/components/settings/CsvDropzone'
import { ImportErrorList } from '@/components/settings/ImportErrorList'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useTrackingLists } from '@/hooks/useTrackingLists'
import { getErrorMessage } from '@/lib/errors'
import { validateCsvFile } from '@/lib/files'
import { importAsins, type AsinImportResult } from '@/services/importService'

const NEW_LIST = 'new'

export function AsinImport() {
  const { lists, reload } = useTrackingLists()
  const [target, setTarget] = useState<string>(NEW_LIST)
  const [newName, setNewName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<AsinImportResult | null>(null)

  const isNew = target === NEW_LIST
  const canSubmit = file !== null && !fileError && (!isNew || newName.trim() !== '') && !submitting

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
      const res = await importAsins(
        file,
        isNew ? { newListName: newName.trim() } : { trackingListId: Number(target) },
      )
      setResult(res)
      setFile(null)
      await reload()
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Import failed. Please check the file and try again.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-3">
      <h3 className="font-medium">Import ASINs into a tracking list</h3>
      <p className="text-sm text-muted-foreground">
        Upload a CSV with one ASIN per row.
      </p>
      <label className="flex flex-col gap-1 text-sm">
        Destination list
        <select
          className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          value={target}
          disabled={submitting}
          onChange={(e) => setTarget(e.target.value)}
        >
          <option value={NEW_LIST}>Create a new list</option>
          {lists.map((l) => (
            <option key={l.id} value={String(l.id)}>
              {l.name} ({l.product_count})
            </option>
          ))}
        </select>
      </label>
      {isNew && (
        <label className="flex flex-col gap-1 text-sm">
          New list name
          <Input
            value={newName}
            maxLength={100}
            disabled={submitting}
            onChange={(e) => setNewName(e.target.value)}
          />
        </label>
      )}
      <CsvDropzone label="ASIN CSV file" file={file} disabled={submitting} onFile={onFile} />
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
      <Button type="button" disabled={!canSubmit} onClick={() => void onSubmit()}>
        {submitting ? 'Importing...' : 'Import ASINs'}
      </Button>
      {result && (
        <div role="status" className="space-y-2 text-sm">
          <p>
            Added {result.added}, skipped {result.skipped}.
          </p>
          <ImportErrorList errors={result.errors} />
        </div>
      )}
    </div>
  )
}
