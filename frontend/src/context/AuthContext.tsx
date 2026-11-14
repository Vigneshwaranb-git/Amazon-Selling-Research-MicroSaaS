import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { refreshSession } from '@/services/api'
import * as authService from '@/services/authService'
import type { RegisterPayload, UpdateProfilePayload } from '@/services/authService'
import type { User } from '@/types'

interface AuthContextType {
  user: User | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (payload: RegisterPayload) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
  updateProfile: (payload: UpdateProfilePayload) => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)

  useEffect(() => {
    // Restore the session from the HttpOnly refresh cookie; a 401 just means "logged out".
    let cancelled = false
    refreshSession()
      .then(() => authService.getMe())
      .then((me) => {
        if (!cancelled) setUser(me)
      })
      .catch(() => {
        if (!cancelled) setUser(null)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const refreshUser = useCallback(async () => {
    setUser(await authService.getMe())
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    await authService.login(email, password)
    setUser(await authService.getMe())
  }, [])

  const register = useCallback(async (payload: RegisterPayload) => {
    await authService.register(payload)
  }, [])

  const logout = useCallback(async () => {
    await authService.logout()
    setUser(null)
  }, [])

  const updateProfile = useCallback(async (payload: UpdateProfilePayload) => {
    setUser(await authService.updateMe(payload))
  }, [])

  const value = useMemo(
    () => ({ user, isLoading, login, register, logout, refreshUser, updateProfile }),
    [user, isLoading, login, register, logout, refreshUser, updateProfile],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
