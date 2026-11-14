import api from '@/services/api'

export interface NotificationSettings {
  bsr_alerts_enabled: boolean
}

export async function getNotificationSettings(): Promise<NotificationSettings> {
  const { data } = await api.get<NotificationSettings>('/settings/notifications')
  return data
}

export async function updateNotificationSettings(
  settings: NotificationSettings,
): Promise<NotificationSettings> {
  const { data } = await api.put<NotificationSettings>('/settings/notifications', settings)
  return data
}
