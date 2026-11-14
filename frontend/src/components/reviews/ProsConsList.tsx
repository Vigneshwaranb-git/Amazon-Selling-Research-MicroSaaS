import { cn } from '@/lib/utils'

interface ProsConsListProps {
  title: string
  items: string[]
  tone: 'pro' | 'con'
}

export function ProsConsList({ title, items, tone }: ProsConsListProps) {
  return (
    <section aria-label={title} className="space-y-2">
      <h3 className={cn('text-sm font-semibold', tone === 'pro' ? 'text-emerald-700' : 'text-red-700')}>
        {title}
      </h3>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">None identified.</p>
      ) : (
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {items.map((item, i) => (
            <li key={`${i}-${item}`}>{item}</li>
          ))}
        </ul>
      )}
    </section>
  )
}
