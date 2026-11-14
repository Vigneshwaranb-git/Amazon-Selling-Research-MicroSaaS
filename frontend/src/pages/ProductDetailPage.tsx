import { Link, useParams } from 'react-router-dom'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { BsrChart } from '@/components/products/BsrChart'
import { SalesChart } from '@/components/products/SalesChart'
import { AddToListButton } from '@/components/products/AddToListButton'
import { Button } from '@/components/ui/button'
import { useProduct, useProductHistory } from '@/hooks/useProducts'

export default function ProductDetailPage() {
  const { asin = '' } = useParams<{ asin: string }>()
  const product = useProduct(asin)
  const history = useProductHistory(asin)

  return (
    <PageWrapper>
      <main className="mx-auto max-w-5xl space-y-6 p-8">
        <Link to="/dashboard" className="text-sm text-muted-foreground hover:underline">
          Back to dashboard
        </Link>
        {product.loading && <p role="status">Loading product...</p>}
        {product.error && (
          <div role="alert" className="space-y-2">
            <p className="text-destructive">{product.error}</p>
            <Button variant="outline" onClick={product.reload}>
              Retry
            </Button>
          </div>
        )}
        {product.data && (
          <>
            <header className="space-y-1">
              <h1 className="text-2xl font-bold">{product.data.title}</h1>
              <p className="text-sm text-muted-foreground">
                {product.data.asin} {product.data.brand ? `· ${product.data.brand}` : ''}
              </p>
              <AddToListButton asin={product.data.asin} />
            </header>
            {history.loading && <p role="status">Loading history...</p>}
            {history.error && (
              <p role="alert" className="text-destructive">
                {history.error}
              </p>
            )}
            {history.data && (
              <div className="grid gap-6 lg:grid-cols-2">
                <BsrChart history={history.data} />
                <SalesChart history={history.data} />
              </div>
            )}
          </>
        )}
      </main>
    </PageWrapper>
  )
}
