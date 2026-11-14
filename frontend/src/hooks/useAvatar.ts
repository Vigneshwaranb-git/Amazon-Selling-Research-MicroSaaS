import axios from 'axios'
import { useCallback, useEffect, useState } from 'react'
import { getErrorMessage } from '@/lib/errors'
import { validateAvatarFile } from '@/lib/files'
import { deleteAvatar, fetchAvatarBlob, uploadAvatar } from '@/services/uploadService'

export interface UseAvatar {
  /** Object URL of the avatar, or null when none exists (callers fall back to initials). */
  url: string | null
  loading: boolean
  busy: boolean
  error: string | null
  upload: (file: File) => Promise<boolean>
  remove: () => Promise<void>
}

export function useAvatar(): UseAvatar {
  const [url, setUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null
    fetchAvatarBlob()
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setUrl(null)
        // 404 simply means no avatar has been uploaded yet.
        if (!(axios.isAxiosError(err) && err.response?.status === 404)) {
          setError(getErrorMessage(err, 'Could not load your avatar.'))
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [tick])

  const upload = useCallback(async (file: File): Promise<boolean> => {
    const invalid = validateAvatarFile(file)
    if (invalid) {
      setError(invalid)
      return false
    }
    setBusy(true)
    setError(null)
    try {
      await uploadAvatar(file)
      setTick((t) => t + 1)
      return true
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Could not upload your avatar.'))
      return false
    } finally {
      setBusy(false)
    }
  }, [])

  const remove = useCallback(async () => {
    setBusy(true)
    setError(null)
    try {
      await deleteAvatar()
      setTick((t) => t + 1)
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Could not remove your avatar.'))
    } finally {
      setBusy(false)
    }
  }, [])

  return { url, loading, busy, error, upload, remove }
}
