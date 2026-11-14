import { useState } from 'react'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { ListManager } from '@/components/tracking/ListManager'
import { TrackedProductTable } from '@/components/tracking/TrackedProductTable'
import { useTrackingListDetail, useTrackingLists } from '@/hooks/useTrackingLists'

export default function TrackingListsPage() {
  const { lists, loading, error, create, rename, remove, removeProduct } = useTrackingLists()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const selected = lists.find((l) => l.id === selectedId) ?? lists[0] ?? null
  const detail = useTrackingListDetail(selected?.id ?? null)
  const products = detail.list && detail.list.id === selected?.id ? detail.list.products : null

  const onRemoveProduct = async (listId: number, asin: string): Promise<void> => {
    try {
      await removeProduct(listId, asin) // refreshes the summaries (product counts)
      detail.reload() // refreshes only the selected list
    } catch {
      // error surfaced by useTrackingLists
    }
  }

  return (
    <PageWrapper>
      <main className="mx-auto max-w-5xl space-y-6 p-8">
        <h1 className="text-2xl font-bold">Tracking Lists</h1>
        {loading && <p role="status">Loading lists...</p>}
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
        {!loading && (
          <div className="grid gap-6 md:grid-cols-[280px_1fr]">
            <ListManager
              lists={lists}
              selectedId={selected?.id ?? null}
              onSelect={setSelectedId}
              onCreate={create}
              onRename={rename}
              onDelete={remove}
            />
            {selected && (
              <section aria-label={selected.name}>
                <h2 className="mb-2 font-semibold">{selected.name}</h2>
                {detail.loading && !products && <p role="status">Loading products...</p>}
                {detail.error && (
                  <p role="alert" className="text-destructive">
                    {detail.error}
                  </p>
                )}
                {products && (
                  <TrackedProductTable
                    products={products}
                    onRemove={(asin) => void onRemoveProduct(selected.id, asin)}
                  />
                )}
              </section>
            )}
          </div>
        )}
      </main>
    </PageWrapper>
  )
}
