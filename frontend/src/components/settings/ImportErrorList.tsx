import type { ImportRowError } from '@/services/importService'

/** Scrollable per-row error list for import results. */
export function ImportErrorList({ errors }: { errors: ImportRowError[] }) {
  if (errors.length === 0) return null
  return (
    <div className="space-y-1">
      <p className="text-sm font-medium text-destructive">
        {errors.length} row{errors.length === 1 ? '' : 's'} had problems
      </p>
      <ul
        aria-label="Import row errors"
        className="max-h-48 space-y-1 overflow-y-auto rounded-md border p-2 text-sm"
      >
        {errors.map((e, i) => (
          <li key={`${e.row}-${i}`}>
            <span className="font-medium">Row {e.row}:</span> {e.message}
          </li>
        ))}
      </ul>
    </div>
  )
}
