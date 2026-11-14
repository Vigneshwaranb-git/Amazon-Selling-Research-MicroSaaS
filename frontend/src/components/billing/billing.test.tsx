import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { PlanCard, type PlanDefinition } from '@/components/billing/PlanCard'
import { SubscriptionStatus } from '@/components/billing/SubscriptionStatus'

const pro: PlanDefinition = {
  tier: 'pro',
  name: 'Pro',
  priceLabel: '$29 / mo',
  description: 'For sellers',
  features: ['Feature A', 'Feature B'],
}

describe('PlanCard', () => {
  it('renders features and calls onSelect', async () => {
    const onSelect = vi.fn()
    render(<PlanCard plan={pro} isCurrent={false} onSelect={onSelect} />)
    expect(screen.getByText('Feature A')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /upgrade to pro/i }))
    expect(onSelect).toHaveBeenCalledWith('pro')
  })

  it('disables the button for the current plan', () => {
    render(<PlanCard plan={pro} isCurrent onSelect={vi.fn()} />)
    expect(screen.getByRole('button', { name: /current plan/i })).toBeDisabled()
  })
})

describe('SubscriptionStatus', () => {
  it('shows status and renewal date for a paid plan', () => {
    render(
      <MemoryRouter>
        <SubscriptionStatus subscription={{ plan: 'pro', status: 'active', current_period_end: '2026-12-01T00:00:00Z' }} />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('subscription-status')).toHaveTextContent('Active')
    expect(screen.getByTestId('period-end')).toHaveTextContent('December 1, 2026')
    expect(screen.queryByRole('link', { name: /upgrade plan/i })).not.toBeInTheDocument()
  })

  it('shows an upgrade CTA on the free plan', () => {
    render(
      <MemoryRouter>
        <SubscriptionStatus subscription={{ plan: 'free', status: 'inactive', current_period_end: null }} />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: /upgrade plan/i })).toHaveAttribute('href', '/pricing')
  })
})
