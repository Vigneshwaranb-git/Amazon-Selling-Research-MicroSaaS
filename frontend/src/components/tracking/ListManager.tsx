import { useState, type FormEvent } from 'react'
import { Pencil, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import type { TrackingListSummary } from '@/types'

interface Props {
  lists: TrackingListSummary[]
  selectedId: number | null
  onSelect: (id: number) => void
  onCreate: (name: string) => Promise<void>
  onRename: (id: number, name: string) => Promise<void>
  onDelete: (id: number) => Promise<void>
}

export function ListManager({ lists, selectedId, onSelect, onCreate, onRename, onDelete }: Props) {
  const [name, setName] = useState('')

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    try {
      await onCreate(trimmed)
      setName('')
    } catch {
      // error surfaced by useTrackingLists
    }
  }

  const rename = (list: TrackingListSummary) => {
    const next = window.prompt('Rename list', list.name)?.trim()
    if (next && next !== list.name) onRename(list.id, next).catch(() => undefined)
  }

  return (
    <div className="space-y-3">
      <form onSubmit={(e) => void submit(e)} className="flex gap-2">
        <Input
          aria-label="New list name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New list name"
        />
        <Button type="submit" disabled={!name.trim()}>
          Create
        </Button>
      </form>
      {lists.length === 0 ? (
        <p className="text-sm text-muted-foreground">No lists yet. Create your first one.</p>
      ) : (
        <ul className="space-y-1">
          {lists.map((l) => (
            <li
              key={l.id}
              className={cn(
                'flex items-center justify-between rounded-md px-2 py-1',
                l.id === selectedId && 'bg-accent',
              )}
            >
              <button type="button" className="flex-1 text-left text-sm" onClick={() => onSelect(l.id)}>
                {l.name} <span className="text-xs text-muted-foreground">({l.product_count})</span>
              </button>
              <Button variant="ghost" size="icon" aria-label={`Rename ${l.name}`} onClick={() => rename(l)}>
                <Pencil className="size-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Delete ${l.name}`}
                onClick={() => onDelete(l.id).catch(() => undefined)}
              >
                <Trash2 className="size-4" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
