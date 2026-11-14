export const MAX_AVATAR_BYTES = 2 * 1024 * 1024
export const MAX_CSV_BYTES = 1024 * 1024
export const AVATAR_TYPES: readonly string[] = ['image/png', 'image/jpeg', 'image/webp']
export const AVATAR_ACCEPT = 'image/png,image/jpeg,image/webp'
export const CSV_ACCEPT = '.csv,text/csv'

/** Returns an error message, or null when the avatar file is acceptable. */
export function validateAvatarFile(file: File): string | null {
  if (!AVATAR_TYPES.includes(file.type)) return 'Avatar must be a PNG, JPEG or WebP image.'
  if (file.size > MAX_AVATAR_BYTES) return 'Avatar must be 2 MB or smaller.'
  return null
}

/** Returns an error message, or null when the CSV file is acceptable. */
export function validateCsvFile(file: File): string | null {
  if (!file.name.toLowerCase().endsWith('.csv')) return 'Please choose a .csv file.'
  if (file.size === 0) return 'The selected file is empty.'
  if (file.size > MAX_CSV_BYTES) return 'CSV must be 1 MB or smaller.'
  return null
}

/** Download a Blob through a temporary anchor, revoking the object URL afterwards. */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
