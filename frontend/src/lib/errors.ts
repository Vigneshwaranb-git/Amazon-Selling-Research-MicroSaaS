import axios from 'axios'

export const DEFAULT_ERROR_MESSAGE = 'Something went wrong. Please try again.'
export const NETWORK_ERROR_MESSAGE = 'Unable to reach the server. Check your connection.'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function nonEmpty(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value : null
}

/**
 * Extract a user-facing message from an API error.
 * Order: `{error: {message}}`, string `detail`, first 422 `detail[].msg`, then the fallback.
 */
export function getErrorMessage(error: unknown, fallback: string = DEFAULT_ERROR_MESSAGE): string {
  if (!axios.isAxiosError(error)) return fallback
  if (!error.response) return NETWORK_ERROR_MESSAGE
  const data: unknown = error.response.data
  if (!isRecord(data)) return fallback

  const apiError = data.error
  if (isRecord(apiError)) {
    const message = nonEmpty(apiError.message)
    if (message) return message
  }

  const detail = data.detail
  const asString = nonEmpty(detail)
  if (asString) return asString
  if (Array.isArray(detail) && isRecord(detail[0])) {
    const msg = nonEmpty(detail[0].msg)
    if (msg) return msg
  }
  return fallback
}
