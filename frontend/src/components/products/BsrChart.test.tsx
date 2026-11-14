import { render, screen } from '@testing-library/react'
import { BsrChart } from '@/components/products/BsrChart'
import type { BsrSnapshot } from '@/types'

const one: BsrSnapshot[] = [
  { id: 0, product_id: 0, bsr: 4321, price: 10, estimated_sales: 100, captured_at: '2025-01-05T00:00:00Z' },
]

describe('BsrChart single point', () => {
  it('shows the snapshot with building-history copy for non-dataset providers', () => {
    render(<BsrChart history={one} provider="mock" />)
    expect(screen.getByText('#4,321')).toBeInTheDocument()
    expect(screen.getByText('Snapshot (Jan 5, 2025)')).toBeInTheDocument()
    expect(screen.getByText(/Only one data point so far; history builds as snapshots are collected/)).toBeInTheDocument()
  })

  it('says the dataset provides a single snapshot for the dataset provider', () => {
    render(<BsrChart history={one} provider="dataset" />)
    expect(screen.getByText('This dataset provides a single snapshot.')).toBeInTheDocument()
    expect(screen.queryByText(/Only one data point/)).not.toBeInTheDocument()
  })
})
