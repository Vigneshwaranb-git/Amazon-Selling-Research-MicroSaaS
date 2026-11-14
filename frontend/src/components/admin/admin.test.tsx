import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { UserTable } from '@/components/admin/UserTable'
import { TotalsCards } from '@/components/analytics/TotalsCards'
import { BsrTrendChart } from '@/components/analytics/BsrTrendChart'
import { TrendDistributionChart } from '@/components/analytics/TrendDistributionChart'
import { TopMovers } from '@/components/analytics/TopMovers'
import type { AdminUser } from '@/types/admin'
import type { AnalyticsOverview } from '@/types/analytics'

function makeUser(over: Partial<AdminUser>): AdminUser {
  return {
    id: 1,
    email: 'u@x.com',
    full_name: null,
    is_active: true,
    is_admin: false,
    is_verified: true,
    oauth_provider: null,
    created_at: '2026-01-01T00:00:00Z',
    plan: 'free',
    ...over,
  }
}

describe('UserTable', () => {
  const me = makeUser({ id: 1, email: 'me@x.com', is_admin: true })
  const other = makeUser({ id: 2, email: 'other@x.com' })

  it('disables deactivate and demote for the current user only', () => {
    render(<UserTable users={[me, other]} currentUserId={1} onUpdate={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Deactivate me@x.com' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Demote me@x.com' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Deactivate other@x.com' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Promote other@x.com' })).toBeEnabled()
  })

  it('requires confirmation before updating', async () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined)
    render(<UserTable users={[other]} currentUserId={1} onUpdate={onUpdate} />)
    await userEvent.click(screen.getByRole('button', { name: 'Deactivate other@x.com' }))
    expect(onUpdate).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onUpdate).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Promote other@x.com' }))
    await userEvent.click(screen.getByRole('button', { name: 'Promote to admin' }))
    expect(onUpdate).toHaveBeenCalledWith(2, { is_admin: true })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('keeps the dialog open and shows the error when the update fails', async () => {
    const onUpdate = vi.fn().mockRejectedValue(new Error('boom'))
    render(<UserTable users={[other]} currentUserId={1} onUpdate={onUpdate} />)
    await userEvent.click(screen.getByRole('button', { name: 'Deactivate other@x.com' }))
    await userEvent.click(screen.getByRole('button', { name: 'Deactivate' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('shows an empty state', () => {
    render(<UserTable users={[]} currentUserId={1} onUpdate={vi.fn()} />)
    expect(screen.getByText('No users found.')).toBeInTheDocument()
  })
})

const empty: AnalyticsOverview = {
  totals: { tracking_lists: 0, tracked_products: 0, scenarios: 0 },
  avg_scenario_margin: null,
  trend_distribution: { rising: 0, stable: 0, declining: 0 },
  bsr_series: [],
  top_movers: [],
}

describe('analytics empty states', () => {
  it('renders N/A margin and empty messages', () => {
    render(
      <MemoryRouter>
        <TotalsCards data={empty} />
        <BsrTrendChart series={empty.bsr_series} />
        <TrendDistributionChart distribution={empty.trend_distribution} />
        <TopMovers movers={empty.top_movers} />
      </MemoryRouter>,
    )
    expect(screen.getByText('N/A')).toBeInTheDocument()
    expect(screen.getByText(/No BSR data/)).toBeInTheDocument()
    expect(screen.getByText(/No tracked products to classify/)).toBeInTheDocument()
    expect(screen.getByText('No movers in this range.')).toBeInTheDocument()
  })

  it('renders distribution table fallback and movers', () => {
    render(
      <MemoryRouter>
        <TrendDistributionChart distribution={{ rising: 3, stable: 1, declining: 0 }} />
        <TopMovers movers={[{ asin: 'B0TEST', title: 'Widget', bsr_change_pct: -12.5 }]} />
      </MemoryRouter>,
    )
    expect(screen.getByRole('img', { name: /Rising 3, Stable 1, Declining 0/ })).toBeInTheDocument()
    expect(screen.getByText('Improved 12.5%')).toBeInTheDocument()
  })
})
