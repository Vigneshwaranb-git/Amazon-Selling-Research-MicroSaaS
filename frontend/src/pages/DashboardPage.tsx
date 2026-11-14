import { useState } from 'react'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { FilterBar } from '@/components/products/FilterBar'
import { ProductFeed } from '@/components/products/ProductFeed'
import { useProducts } from '@/hooks/useProducts'
import { DEFAULT_FILTERS, type ProductFilters } from '@/types/products'

export default function DashboardPage() {
  const [filters, setFilters] = useState<ProductFilters>(DEFAULT_FILTERS)
  const { data, loading, error, reload } = useProducts(filters)
  return (
    <PageWrapper>
      <main className="mx-auto max-w-6xl space-y-6 p-8">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <FilterBar filters={filters} onChange={setFilters} />
        <ProductFeed
          data={data}
          loading={loading}
          error={error}
          onRetry={reload}
          onPage={(page) => setFilters({ ...filters, page })}
        />
      </main>
    </PageWrapper>
  )
}
