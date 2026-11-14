import { useDataSource } from '@/hooks/useDataSource'
import { formatSnapshotDate } from '@/lib/dates'

/** Footer notice that tells users where the figures come from. Renders nothing if unknown. */
export function DataSourceNotice() {
  const source = useDataSource()
  if (!source) return null

  if (source.provider === 'mock') {
    return (
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span className="rounded-full border border-amber-500 bg-amber-50 px-2 py-0.5 font-medium text-amber-900">
          Demo data - sample figures, not real Amazon data
        </span>
      </div>
    )
  }

  return (
    <div className="space-y-1 text-xs text-muted-foreground">
      {source.attribution && <p>{source.attribution}</p>}
      {source.data_as_of && <p>Data snapshot as of {formatSnapshotDate(source.data_as_of)}</p>}
      {source.notes.length > 0 && (
        <details>
          <summary className="cursor-pointer rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            About this data
          </summary>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {source.notes.map((note, index) => (
              <li key={`${index}-${note}`}>{note}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
