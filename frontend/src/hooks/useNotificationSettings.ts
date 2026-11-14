import { useCallback, useEffect, useState } from 'react'
import { getErrorMessage } from '@/lib/errors'
import { getNotificationSettings, updateNotificationSettings } from '@/services/settingsService'

export interface UseNotificationSettings {
  enabled: boolean
  loading: boolean
  saving: boolean
  error: string | null
  setEnabled: (value: boolean) => Promise<void>
}

export function useNotificationSettings(): UseNotificationSettings {
  const [enabled, setEnabledState] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getNotificationSettings()
      .then((s) => {
        if (!cancelled) setEnabledState(s.bsr_alerts_enabled)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(getErrorMessage(err, 'Could not load notification settings.'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const setEnabled = useCallback(async (value: boolean) => {
    setSaving(true)
    setError(null)
    try {
      const saved = await updateNotificationSettings({ bsr_alerts_enabled: value })
      setEnabledState(saved.bsr_alerts_enabled)
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Could not save your notification settings.'))
    } finally {
      setSaving(false)
    }
  }, [])

  return { enabled, loading, saving, error, setEnabled }
}
