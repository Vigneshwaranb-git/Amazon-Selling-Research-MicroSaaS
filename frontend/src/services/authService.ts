import api, { setAccessToken } from '@/services/api'
import type { AccessToken, User } from '@/types'

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

interface MessageResponse {
  message: string
}

const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export function getGoogleLoginUrl(): string {
  return `${API_URL}/api/v1/auth/google`
}

/** Signs in; the refresh cookie is set by the server and the access token is kept in memory. */
export async function login(email: string, password: string): Promise<void> {
  const form = new URLSearchParams()
  form.append('username', email)
  form.append('password', password)
  const { data } = await api.post<AccessToken>('/auth/login', form)
  setAccessToken(data.access_token)
}

/** Creates an unverified account. The user must verify their email before signing in. */
export async function register(payload: RegisterPayload): Promise<User> {
  const { data } = await api.post<User>('/auth/register', payload)
  return data
}

export async function logout(): Promise<void> {
  try {
    await api.post('/auth/logout')
  } catch {
    // Revocation is best effort; the local session is cleared regardless.
  } finally {
    setAccessToken(null)
  }
}

export async function getMe(): Promise<User> {
  const { data } = await api.get<User>('/auth/me')
  return data
}

export async function updateMe(payload: UpdateProfilePayload): Promise<User> {
  const { data } = await api.put<User>('/auth/me', payload)
  return data
}

export async function forgotPassword(email: string): Promise<void> {
  await api.post('/auth/forgot-password', { email })
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
  await api.post('/auth/reset-password', { token, new_password: newPassword })
}

export async function verifyEmail(token: string): Promise<string> {
  const { data } = await api.post<MessageResponse>('/auth/verify-email', { token })
  return data.message
}

export async function resendVerification(email: string): Promise<string> {
  const { data } = await api.post<MessageResponse>('/auth/resend-verification', { email })
  return data.message
}
