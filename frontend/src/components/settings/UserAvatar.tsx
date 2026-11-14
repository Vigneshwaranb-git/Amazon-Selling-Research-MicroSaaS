import { cn } from '@/lib/utils'

interface UserAvatarProps {
  url: string | null
  name: string
  className?: string
}

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  const letters = parts.slice(0, 2).map((p) => p[0]?.toUpperCase() ?? '')
  return letters.join('') || '?'
}

/** Avatar image, falling back to initials when no image exists. */
export function UserAvatar({ url, name, className }: UserAvatarProps) {
  if (url) {
    return (
      <img
        src={url}
        alt={`${name} avatar`}
        className={cn('size-16 rounded-full object-cover', className)}
      />
    )
  }
  return (
    <span
      role="img"
      aria-label={`${name} avatar (initials)`}
      className={cn(
        'flex size-16 items-center justify-center rounded-full bg-secondary text-lg font-semibold',
        className,
      )}
    >
      {initialsOf(name)}
    </span>
  )
}
