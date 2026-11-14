import { Button } from '@/components/ui/button'
import { ProductCard } from '@/components/products/ProductCard'
import type { ProductPage } from '@/types/products'

interface ProductFeedProps {
  data: ProductPage | null
  loading: boolean
  error: string | null
  onRetry: () => void
  onPage: (page: number) => void
}

export function ProductFeed({ data, loading, error, onRetry, onPage }: ProductFeedProps) {
  if (error) {
    return (
      <div role="alert" className="rounded-xl border border-destructive/40 p-6 text-center">
        <p className="text-destructive">{error}</p>
        <Button className="mt-3" variant="outline" onClick={onRetry}>
          Retry
        </Button>
      </div>
    )
  }
  if (loading && !data) {
    return (
      <div role="status" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="h-44 animate-pulse rounded-2xl bg-muted" />
        ))}
        <span className="sr-only">Loading products</span>
      </div>
    )
  }
  if (!data || data.items.length === 0) {
    return (
      <p className="rounded-xl border p-8 text-center text-muted-foreground">
        No products match your filters.
      </p>
    )
  }
  const totalPages = data.page_size > 0 ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  return (
    <div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.items.map((p) => (
          <ProductCard key={p.asin} product={p} />
        ))}
      </div>
      {totalPages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-3">
          <Button variant="outline" disabled={data.page <= 1} onClick={() => onPage(data.page - 1)}>
            Previous
          </Button>
          <span className="text-sm">
            Page {data.page} of {totalPages}
          </span>
          <Button
            variant="outline"
            disabled={data.page >= totalPages}
            onClick={() => onPage(data.page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
