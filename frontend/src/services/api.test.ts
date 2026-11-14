import axios, { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import api, { getAccessToken, refreshSession, setAccessToken } from '@/services/api'

const postSpy = vi.spyOn(axios, 'post')
const assign = vi.fn()

function respond(config: InternalAxiosRequestConfig, status: number, data: unknown) {
  const response = { data, status, statusText: '', headers: {}, config }
  if (status >= 400) return Promise.reject(new AxiosError('fail', String(status), config, null, response))
  return Promise.resolve(response)
}

beforeEach(() => {
  setAccessToken(null)
  localStorage.clear()
  postSpy.mockReset()
  assign.mockReset()
  vi.stubGlobal('location', { ...window.location, pathname: '/dashboard', assign })
})
afterEach(() => {
  vi.unstubAllGlobals()
})

describe('api client', () => {
  it('sends credentials and the in-memory bearer token', async () => {
    expect(api.defaults.withCredentials).toBe(true)
    setAccessToken('mem-token')
    let auth: unknown
    const adapter: AxiosAdapter = (config) => {
      auth = config.headers.Authorization
      return respond(config, 200, {})
    }
    await api.get('/x', { adapter })
    expect(auth).toBe('Bearer mem-token')
  })

  it('refreshSession sends the CSRF header, no body, and never touches storage', async () => {
    postSpy.mockResolvedValue({ data: { access_token: 'new', token_type: 'bearer' } })
    await refreshSession()
    const [url, body, config] = postSpy.mock.calls[0]
    expect(String(url)).toMatch(/\/auth\/refresh$/)
    expect(body).toBeNull()
    expect(config?.headers).toMatchObject({ 'X-Requested-With': 'XMLHttpRequest' })
    expect(config?.withCredentials).toBe(true)
    expect(getAccessToken()).toBe('new')
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })

  it('shares a single refresh across concurrent 401s, then retries each request', async () => {
    setAccessToken('old')
    let resolveRefresh: (v: unknown) => void = () => {}
    postSpy.mockReturnValue(new Promise((r) => (resolveRefresh = r)))
    const adapter: AxiosAdapter = (config) =>
      respond(config, config.headers.Authorization === 'Bearer new' ? 200 : 401, { ok: true })
    const calls = [api.get('/a', { adapter }), api.get('/b', { adapter }), api.get('/c', { adapter })]
    await vi.waitFor(() => expect(postSpy).toHaveBeenCalledTimes(1))
    resolveRefresh({ data: { access_token: 'new', token_type: 'bearer' } })
    const results = await Promise.all(calls)
    expect(results.map((r) => r.status)).toEqual([200, 200, 200])
    expect(postSpy).toHaveBeenCalledTimes(1)
  })

  it('clears the token and goes to /login when refresh fails', async () => {
    setAccessToken('old')
    postSpy.mockRejectedValue(new Error('401'))
    const adapter: AxiosAdapter = (config) => respond(config, 401, {})
    await expect(api.get('/a', { adapter })).rejects.toBeTruthy()
    expect(getAccessToken()).toBeNull()
    expect(assign).toHaveBeenCalledWith('/login')
  })

  it('does not try to refresh on a 401 from /auth/login', async () => {
    const adapter: AxiosAdapter = (config) => respond(config, 401, {})
    await expect(api.post('/auth/login', 'x', { adapter })).rejects.toBeTruthy()
    expect(postSpy).not.toHaveBeenCalled()
    expect(assign).not.toHaveBeenCalled()
  })
})
