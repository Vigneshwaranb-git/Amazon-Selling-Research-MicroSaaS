import { useId, useState } from 'react'
import { UserAvatar } from '@/components/settings/UserAvatar'
import { Button } from '@/components/ui/button'
import { useAvatar } from '@/hooks/useAvatar'
import { AVATAR_ACCEPT } from '@/lib/files'

interface AvatarUploaderProps {
  name: string
}

export function AvatarUploader({ name }: AvatarUploaderProps) {
  const { url, loading, busy, error, upload, remove } = useAvatar()
  const inputId = useId()
  const [done, setDone] = useState(false)

  return (
    <div className="flex flex-wrap items-center gap-4">
      <UserAvatar url={url} name={name} />
      <div className="space-y-2">
        <label htmlFor={inputId} className="block text-sm font-medium">
          Upload avatar
        </label>
        <input
          id={inputId}
          type="file"
          accept={AVATAR_ACCEPT}
          disabled={busy || loading}
          className="block text-sm"
          onChange={(e) => {
            const file = e.target.files?.[0]
            e.target.value = ''
            if (!file) return
            setDone(false)
            void upload(file).then(setDone)
          }}
        />
        <p className="text-xs text-muted-foreground">PNG, JPEG or WebP, up to 2 MB.</p>
        {url && (
          <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => void remove()}>
            Remove avatar
          </Button>
        )}
        {busy && <p className="text-sm">Working...</p>}
        {done && !busy && !error && (
          <p role="status" className="text-sm">
            Avatar updated.
          </p>
        )}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </div>
    </div>
  )
}
