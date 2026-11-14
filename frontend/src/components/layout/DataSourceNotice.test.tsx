import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DataSourceNotice } from '@/components/layout/DataSourceNotice'
import { resetDataSourceCache } from '@/hooks/useDataSource'
import { fetchDataSource } from '@/services/metaService'

vi.mock('@/services/metaService')
const mockedFetch = vi.mocked(fetchDataSource)

describe('DataSourceNotice', () => {
  beforeEach(() => {
    resetDataSourceCache()
    mockedFetch.mockReset()
  })

  it('shows a demo badge for the mock provider', async () => {
    mockedFetch.mockResolvedValue({ provider: 'mock', attribution: null, data_as_of: null, notes: [] })
    render(<DataSourceNotice />)
    expect(await screen.findByText('Demo data - sample figures, not real Amazon data')).toBeInTheDocument()
  })

  it('shows attribution, snapshot date and notes for the dataset provider as plain text', async () => {
    mockedFetch.mockResolvedValue({
      provider: 'dataset',
      attribution: 'Source: <b>Example</b> dataset',
      data_as_of: '2025-01-05',
      notes: ['Sales are estimated.'],
    })
    const user = userEvent.setup()
    render(<DataSourceNotice />)
    expect(await screen.findByText('Source: <b>Example</b> dataset')).toBeInTheDocument()
    expect(screen.getByText('Data snapshot as of Jan 5, 2025')).toBeInTheDocument()
    await user.click(screen.getByText('About this data'))
    expect(screen.getByText('Sales are estimated.')).toBeInTheDocument()
    expect(screen.queryByText('Demo data - sample figures, not real Amazon data')).not.toBeInTheDocument()
  })

  it('renders nothing when the request fails', async () => {
    mockedFetch.mockRejectedValue(new Error('boom'))
    const { container } = render(<DataSourceNotice />)
    await vi.waitFor(() => expect(mockedFetch).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })
})
