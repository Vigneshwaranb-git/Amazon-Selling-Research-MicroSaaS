import { render, screen } from '@testing-library/react'
import App from '@/App'

describe('App', () => {
  it('renders the pricing placeholder route', () => {
    window.history.pushState({}, '', '/pricing')
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Pricing' })).toBeInTheDocument()
  })
})
