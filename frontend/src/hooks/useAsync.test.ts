import { describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { useAsync } from '@/hooks/useAsync'

describe('useAsync', () => {
  it('loads data', async () => {
    const load = vi.fn().mockResolvedValue('ok')
    const { result } = renderHook(() => useAsync(load, 'failed', []))
    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.data).toBe('ok')
    expect(result.current.error).toBeNull()
  })

  it('reports the failure message and can reload', async () => {
    const load = vi.fn().mockRejectedValueOnce(new Error('boom')).mockResolvedValueOnce('later')
    const { result } = renderHook(() => useAsync(load, 'Could not load.', []))
    await waitFor(() => expect(result.current.error).toBe('Could not load.'))
    act(() => result.current.reload())
    await waitFor(() => expect(result.current.data).toBe('later'))
    expect(result.current.error).toBeNull()
    expect(load).toHaveBeenCalledTimes(2)
  })

  it('reloads when deps change', async () => {
    const load = vi.fn((): Promise<string> => Promise.resolve('x'))
    const { rerender } = renderHook(({ id }) => useAsync(load, 'failed', [id]), { initialProps: { id: 'a' } })
    await waitFor(() => expect(load).toHaveBeenCalledTimes(1))
    rerender({ id: 'b' })
    await waitFor(() => expect(load).toHaveBeenCalledTimes(2))
  })
})
