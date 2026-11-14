import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FilterBar } from '@/components/products/FilterBar'
import { DEFAULT_FILTERS } from '@/types/products'

describe('FilterBar', () => {
  it('emits changes and resets page to 1', async () => {
    const onChange = vi.fn()
    render(<FilterBar filters={{ ...DEFAULT_FILTERS, page: 3 }} onChange={onChange} />)
    await userEvent.type(screen.getByLabelText('Category'), 'K')
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ category: 'K', page: 1 }))
  })

  it('resets filters', async () => {
    const onChange = vi.fn()
    render(<FilterBar filters={{ ...DEFAULT_FILTERS, category: 'X' }} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'Reset' }))
    expect(onChange).toHaveBeenCalledWith(DEFAULT_FILTERS)
  })
})
