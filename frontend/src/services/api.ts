import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { AccessToken } from '@/types'

const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const BASE_URL = `${API_URL}/api/v1`

/**
 * The access token lives in memory only (never localStorage/sessionStorage). The refresh token is an
 * HttpOnly cookie that JavaScript cannot read; a page reload recovers the session via /auth/refresh.
 */
let accessToken: string | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token
}

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

const api = axios.create({ baseURL: BASE_URL, withCredentials: true })

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  return config
})

let refreshPromise: Promise<string> | null = null

/**
 * Exchange the refresh cookie for a new access token. Concurrent callers share one request.
 * Uses a bare axios call so the response interceptor can never recurse into it.
 */
export function refreshSession(): Promise<string> {
  refreshPromise ??= axios
    .post<AccessToken>(`${BASE_URL}/auth/refresh`, null, {
      withCredentials: true,
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
    .then(({ data }) => {
      accessToken = data.access_token
      return data.access_token
    })
    .finally(() => {
      refreshPromise = null
    })
  return refreshPromise
}

const NO_RETRY_PATHS = ['/auth/refresh', '/auth/login']

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined
    const skip = NO_RETRY_PATHS.some((p) => original?.url?.includes(p))
    if (error.response?.status === 401 && original && !original._retry && !skip) {
      original._retry = true
      try {
        await refreshSession()
        return api(original)
      } catch (refreshError) {
        accessToken = null
        if (window.location.pathname !== '/login') window.location.assign('/login')
        return Promise.reject(refreshError)
      }
    }
    return Promise.reject(error)
  },
)

export default api
