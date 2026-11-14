import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { TokenPair } from '@/types'

const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const BASE_URL = `${API_URL}/api/v1`

export const ACCESS_TOKEN_KEY = 'access_token'
export const REFRESH_TOKEN_KEY = 'refresh_token'

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

const api = axios.create({ baseURL: BASE_URL })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let refreshPromise: Promise<TokenPair> | null = null

async function refreshTokens(refreshToken: string): Promise<TokenPair> {
  const { data } = await axios.post<TokenPair>(`${BASE_URL}/auth/refresh`, {
    refresh_token: refreshToken,
  })
  localStorage.setItem(ACCESS_TOKEN_KEY, data.access_token)
  localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh_token)
  return data
}

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined
    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true
      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)
      if (!refreshToken) return Promise.reject(error)
      try {
        refreshPromise ??= refreshTokens(refreshToken).finally(() => {
          refreshPromise = null
        })
        await refreshPromise
        return api(original)
      } catch (refreshError) {
        localStorage.removeItem(ACCESS_TOKEN_KEY)
        localStorage.removeItem(REFRESH_TOKEN_KEY)
        window.location.assign('/login')
        return Promise.reject(refreshError)
      }
    }
    return Promise.reject(error)
  },
)

export default api
