import { AxiosError, type AxiosResponse } from 'axios'
import { describe, expect, it } from 'vitest'
import { getErrorMessage, NETWORK_ERROR_MESSAGE } from '@/lib/errors'

function axiosError(data: unknown, status = 400): AxiosError {
  const err = new AxiosError('Request failed')
  err.response = { data, status } as AxiosResponse
  return err
}

describe('getErrorMessage', () => {
  it('prefers error.message', () => {
    const err = axiosError({ error: { code: 'X', message: 'Nope' }, detail: 'other' })
    expect(getErrorMessage(err)).toBe('Nope')
  })
  it('falls back to string detail', () => {
    expect(getErrorMessage(axiosError({ detail: 'Bad thing' }))).toBe('Bad thing')
  })
  it('falls back to first 422 msg', () => {
    expect(getErrorMessage(axiosError({ detail: [{ msg: 'too short' }] }, 422))).toBe('too short')
  })
  it('uses fallback for unknown shapes and non-axios errors', () => {
    expect(getErrorMessage(axiosError({}), 'fb')).toBe('fb')
    expect(getErrorMessage(axiosError('<html>'), 'fb')).toBe('fb')
    expect(getErrorMessage(new Error('raw'), 'fb')).toBe('fb')
  })
  it('reports network errors', () => {
    expect(getErrorMessage(new AxiosError('Network Error'))).toBe(NETWORK_ERROR_MESSAGE)
  })
})
