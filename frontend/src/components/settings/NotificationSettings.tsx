import { useNotificationSettings } from '@/hooks/useNotificationSettings'

export function NotificationSettings() {
  const { enabled, loading, saving, error, setEnabled } = useNotificationSettings()
  return (
    <div className="space-y-2">
      <label className="flex items-center gap-3 text-sm">
        <input
          type="checkbox"
          role="switch"
          checked={enabled}
          disabled={loading || saving}
          onChange={(e) => void setEnabled(e.target.checked)}
        />
        Email me when a tracked product's BSR changes significantly
      </label>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}
