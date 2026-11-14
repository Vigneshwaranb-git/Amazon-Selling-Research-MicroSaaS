import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ProductCard } from '@/components/products/ProductCard'
import type { TrackerProduct } from '@/types/products'

const product: TrackerProduct = {
  id: 1,
  asin: 'B000TEST01',
  title: 'Steel Water Bottle',
  brand: null,
  category: 'Kitchen',
  image_url: null,
  price: 19.99,
  rating: 4.5,
  review_count: 100,
  current_bsr: 1234,
  estimated_monthly_sales: 900,
  created_at: '',
  updated_at: '',
  estimated_margin: 32,
  saturation_score: 40,
  trend: 'rising',
}

describe('ProductCard', () => {
  it('renders details and links to the detail page', () => {
    render(
      <MemoryRouter>
        <ProductCard product={product} />
      </MemoryRouter>,
    )
    expect(screen.getByText('Steel Water Bottle')).toBeInTheDocument()
    expect(screen.getByText('#1,234')).toBeInTheDocument()
    expect(screen.getByText('32%')).toBeInTheDocument()
    expect(screen.getByRole('link')).toHaveAttribute('href', '/products/B000TEST01')
  })
})

describe('ProductCard estimated label', () => {
  it('marks monthly sales as an estimate', () => {
    render(
      <MemoryRouter>
        <ProductCard product={product} />
      </MemoryRouter>,
    )
    expect(screen.getByText('Est.')).toBeInTheDocument()
  })
})
