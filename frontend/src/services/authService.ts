import api, { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from '@/services/api'
import type { TokenPair, User } from '@/types'

export interface RegisterPayload {
  email: string
  password: string
  full_name: string
}

export interface UpdateProfilePayload {
  full_name?: string
  /** Required by the API when `password` is set. */
  current_password?: string
  password?: string
}

const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export function storeTokens(tokens: Pick<TokenPair, 'access_token' | 'refresh_token'>): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token)
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

export function getGoogleLoginUrl(): string {
  return `${API_URL}/api/v1/auth/google`
}

export async function login(email: string, password: string): Promise<TokenPair> {
  const form = new URLSearchParams()
  form.append('username', email)
  form.append('password', password)
  const { data } = await api.post<TokenPair>('/auth/login', form)
  storeTokens(data)
  return data
}

export async function register(payload: RegisterPayload): Promise<User> {
  const { data } = await api.post<User>('/auth/register', payload)
  return data
}

export async function logout(): Promise<void> {
  try {
    await api.post('/auth/logout', { refresh_token: localStorage.getItem(REFRESH_TOKEN_KEY) })
  } catch {
    // Token revocation is best effort; the local session is cleared regardless.
  } finally {
    clearTokens()
  }
}

export async function getMe(): Promise<User> {
  const { data } = await api.get<User>('/auth/me')
  return data
}

type ProfileUpdateResponse = User & { tokens?: Pick<TokenPair, 'access_token' | 'refresh_token'> | null }

export async function updateMe(payload: UpdateProfilePayload): Promise<User> {
  const { data } = await api.put<ProfileUpdateResponse>('/auth/me', payload)
  const { tokens, ...user } = data
  // A password change revokes every refresh token; the API returns a fresh pair for this session.
  if (tokens) storeTokens(tokens)
  return user
}

export async function forgotPassword(email: string): Promise<void> {
  await api.post('/auth/forgot-password', { email })
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
  await api.post('/auth/reset-password', { token, new_password: newPassword })
}
