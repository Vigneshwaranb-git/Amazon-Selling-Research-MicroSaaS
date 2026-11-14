/** Format an ISO date (or datetime) as e.g. "Jan 5, 2025"; falls back to the raw text if unparsable. */
export function formatSnapshotDate(iso: string): string {
  const day = iso.slice(0, 10)
  const date = new Date(`${day}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' })
}
