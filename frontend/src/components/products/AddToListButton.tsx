import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { useTrackingLists } from '@/hooks/useTrackingLists'

export function AddToListButton({ asin }: { asin: string }) {
  const { lists, loading, error, addProduct } = useTrackingLists()
  const [listId, setListId] = useState('')
  const [status, setStatus] = useState<'idle' | 'saving' | 'added' | 'failed'>('idle')

  const submit = async () => {
    if (!listId) return
    setStatus('saving')
    try {
      await addProduct(Number(listId), asin)
      setStatus('added')
    } catch {
      setStatus('failed')
    }
  }

  if (loading) return <p className="text-sm text-muted-foreground">Loading lists...</p>
  if (error && lists.length === 0) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {error}
      </p>
    )
  }
  if (lists.length === 0) {
    return <p className="text-sm text-muted-foreground">Create a tracking list first.</p>
  }

  return (
    <div className="flex items-center gap-2">
      <select
        aria-label="Tracking list"
        className="h-9 rounded-md border border-input bg-background px-3 text-sm"
        value={listId}
        onChange={(e) => {
          setListId(e.target.value)
          setStatus('idle')
        }}
      >
        <option value="">Select list</option>
        {lists.map((l) => (
          <option key={l.id} value={l.id}>
            {l.name}
          </option>
        ))}
      </select>
      <Button onClick={() => void submit()} disabled={!listId || status === 'saving'}>
        {status === 'added' ? 'Added' : 'Add to list'}
      </Button>
      {status === 'failed' && (
        <span role="alert" className="text-sm text-destructive">
          Could not add
        </span>
      )}
    </div>
  )
}
