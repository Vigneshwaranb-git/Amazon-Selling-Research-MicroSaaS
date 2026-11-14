import api from '@/services/api'

/** Upload a new avatar (png/jpeg/webp, max 2 MB). */
export async function uploadAvatar(file: File): Promise<void> {
  const form = new FormData()
  form.append('file', file)
  await api.post('/uploads/avatar', form)
}

/** Fetch the avatar bytes (auth header required). Rejects with a 404 error when none exists. */
export async function fetchAvatarBlob(): Promise<Blob> {
  const { data } = await api.get<Blob>('/uploads/avatar', { responseType: 'blob' })
  return data
}

export async function deleteAvatar(): Promise<void> {
  await api.delete('/uploads/avatar')
}
