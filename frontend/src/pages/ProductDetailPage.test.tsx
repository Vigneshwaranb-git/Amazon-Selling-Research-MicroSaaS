import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ProductDetailPage from '@/pages/ProductDetailPage'
import { resetDataSourceCache } from '@/hooks/useDataSource'
import { fetchDataSource } from '@/services/metaService'
import { fetchProduct, fetchProductHistory } from '@/services/productService'
import type { TrackerProduct } from '@/types/products'

vi.mock('@/services/metaService')
vi.mock('@/services/productService')
vi.mock('@/components/products/AddToListButton', () => ({ AddToListButton: () => null }))
vi.mock('@/components/products/SalesChart', () => ({ SalesChart: () => null }))

const product: TrackerProduct = {
  id: 0,
  asin: 'B000TEST01',
  title: 'Steel Water Bottle',
  brand: null,
  category: null,
  image_url: null,
  price: 19.99,
  rating: null,
  review_count: null,
  current_bsr: 1234,
  estimated_monthly_sales: 900,
  created_at: '',
  updated_at: '',
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/products/B000TEST01']}>
      <Routes>
        <Route path="/products/:asin" element={<ProductDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProductDetailPage data source labels', () => {
  beforeEach(() => {
    resetDataSourceCache()
    vi.mocked(fetchProduct).mockResolvedValue(product)
    vi.mocked(fetchProductHistory).mockResolvedValue([
      { id: 0, product_id: 0, bsr: 1234, price: 19.99, estimated_sales: 900, captured_at: '2025-01-05T00:00:00Z' },
    ])
  })

  it('labels dataset figures as Snapshot and Estimated', async () => {
    vi.mocked(fetchDataSource).mockResolvedValue({
      provider: 'dataset',
      attribution: 'x',
      data_as_of: '2025-01-05',
      notes: [],
    })
    renderPage()
    expect(await screen.findByText('BSR - Snapshot (Jan 5, 2025)')).toBeInTheDocument()
    expect(screen.getByText('Price - Snapshot (Jan 5, 2025)')).toBeInTheDocument()
    expect(screen.getByText('Monthly sales - Estimated')).toBeInTheDocument()
    expect(await screen.findByText('This dataset provides a single snapshot.')).toBeInTheDocument()
  })

  it('does not show snapshot labels for mock data', async () => {
    vi.mocked(fetchDataSource).mockResolvedValue({ provider: 'mock', attribution: null, data_as_of: null, notes: [] })
    renderPage()
    expect(await screen.findByText(/Only one data point so far/)).toBeInTheDocument()
    expect(screen.queryByText(/Monthly sales - Estimated/)).not.toBeInTheDocument()
  })
})
