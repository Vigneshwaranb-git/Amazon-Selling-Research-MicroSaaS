import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, type AxiosResponse } from 'axios'
import { AsinImport } from '@/components/settings/AsinImport'
import { AvatarUploader } from '@/components/settings/AvatarUploader'
import { CostSheetImport } from '@/components/settings/CostSheetImport'
import { NotificationSettings } from '@/components/settings/NotificationSettings'
import { ExportCsvButton } from '@/components/products/ExportCsvButton'
import { validateAvatarFile, validateCsvFile } from '@/lib/files'
import { DEFAULT_FILTERS } from '@/types/products'
import * as importService from '@/services/importService'
import * as settingsService from '@/services/settingsService'
import * as uploadService from '@/services/uploadService'
import * as productService from '@/services/productService'
import * as trackingService from '@/services/trackingService'

vi.mock('@/services/importService')
vi.mock('@/services/settingsService')
vi.mock('@/services/uploadService')
vi.mock('@/services/productService')
vi.mock('@/services/trackingService')

const csv = (name = 'a.csv', body = 'B000000000\n') => new File([body], name, { type: 'text/csv' })

function httpError(status: number): AxiosError {
  return new AxiosError('fail', 'ERR', undefined, undefined, {
    status,
    data: {},
  } as AxiosResponse)
}

beforeEach(() => {
  vi.resetAllMocks()
  URL.createObjectURL = vi.fn(() => 'blob:mock')
  URL.revokeObjectURL = vi.fn()
  vi.mocked(trackingService.fetchTrackingLists).mockResolvedValue([
    { id: 7, name: 'Winners', created_at: '', product_count: 2 },
  ])
})

describe('client-side validation', () => {
  it('rejects bad csv files', () => {
    expect(validateCsvFile(csv('a.txt'))).toMatch(/\.csv/)
    expect(validateCsvFile(csv('a.csv', ''))).toMatch(/empty/)
    expect(validateCsvFile(csv('a.csv', 'x'.repeat(1024 * 1024 + 1)))).toMatch(/1 MB/)
    expect(validateCsvFile(csv())).toBeNull()
  })

  it('rejects bad avatar files', () => {
    expect(validateAvatarFile(new File(['x'], 'a.gif', { type: 'image/gif' }))).toMatch(/PNG/)
    const big = new File([new Uint8Array(2 * 1024 * 1024 + 1)], 'a.png', { type: 'image/png' })
    expect(validateAvatarFile(big)).toMatch(/2 MB/)
    expect(validateAvatarFile(new File(['x'], 'a.webp', { type: 'image/webp' }))).toBeNull()
  })
})

describe('AsinImport', () => {
  it('shows an error and does not upload a non-csv file', async () => {
    render(<AsinImport />)
    await userEvent.upload(screen.getByLabelText('ASIN CSV file'), csv('a.txt'), {
      applyAccept: false,
    })
    expect(await screen.findByRole('alert')).toHaveTextContent('.csv')
    expect(screen.getByRole('button', { name: 'Import ASINs' })).toBeDisabled()
    expect(importService.importAsins).not.toHaveBeenCalled()
  })

  it('renders results with row errors and refreshes list summaries', async () => {
    vi.mocked(importService.importAsins).mockResolvedValue({
      added: 3,
      skipped: 1,
      errors: [{ row: 5, message: 'Invalid ASIN' }],
    })
    render(<AsinImport />)
    await screen.findByRole('option', { name: 'Winners (2)' })
    await userEvent.selectOptions(screen.getByLabelText('Destination list'), '7')
    await userEvent.upload(screen.getByLabelText('ASIN CSV file'), csv())
    await userEvent.click(screen.getByRole('button', { name: 'Import ASINs' }))

    expect(await screen.findByText('Added 3, skipped 1.')).toBeInTheDocument()
    expect(screen.getByText('Invalid ASIN')).toBeInTheDocument()
    expect(screen.getByLabelText('Import row errors')).toBeInTheDocument()
    expect(importService.importAsins).toHaveBeenCalledWith(expect.any(File), { trackingListId: 7 })
    await waitFor(() => expect(trackingService.fetchTrackingLists).toHaveBeenCalledTimes(2))
  })

  it('requires a name for a new list', async () => {
    render(<AsinImport />)
    await userEvent.upload(screen.getByLabelText('ASIN CSV file'), csv())
    expect(screen.getByRole('button', { name: 'Import ASINs' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText('New list name'), 'Fresh')
    expect(screen.getByRole('button', { name: 'Import ASINs' })).toBeEnabled()
  })
})

describe('CostSheetImport', () => {
  it('renders created count and row errors', async () => {
    vi.mocked(importService.importCostSheet).mockResolvedValue({
      created: 2,
      errors: [{ row: 3, message: 'Bad price' }],
    })
    render(<CostSheetImport />)
    await userEvent.upload(screen.getByLabelText('Cost sheet CSV file'), csv())
    await userEvent.click(screen.getByRole('button', { name: 'Import cost sheet' }))
    expect(await screen.findByText('Created 2 scenario(s).')).toBeInTheDocument()
    expect(screen.getByText('Bad price')).toBeInTheDocument()
  })

  it('downloads the template', async () => {
    render(<CostSheetImport />)
    await userEvent.click(screen.getByRole('button', { name: 'Download template' }))
    expect(URL.createObjectURL).toHaveBeenCalled()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock')
  })
})

describe('NotificationSettings', () => {
  it('loads and toggles the setting', async () => {
    vi.mocked(settingsService.getNotificationSettings).mockResolvedValue({
      bsr_alerts_enabled: false,
    })
    vi.mocked(settingsService.updateNotificationSettings).mockResolvedValue({
      bsr_alerts_enabled: true,
    })
    render(<NotificationSettings />)
    const toggle = screen.getByRole('switch')
    await waitFor(() => expect(toggle).toBeEnabled())
    expect(toggle).not.toBeChecked()
    await userEvent.click(toggle)
    await waitFor(() => expect(toggle).toBeChecked())
    expect(settingsService.updateNotificationSettings).toHaveBeenCalledWith({
      bsr_alerts_enabled: true,
    })
  })

  it('shows an error when saving fails', async () => {
    vi.mocked(settingsService.getNotificationSettings).mockResolvedValue({
      bsr_alerts_enabled: false,
    })
    vi.mocked(settingsService.updateNotificationSettings).mockRejectedValue(httpError(500))
    render(<NotificationSettings />)
    const toggle = screen.getByRole('switch')
    await waitFor(() => expect(toggle).toBeEnabled())
    await userEvent.click(toggle)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(toggle).not.toBeChecked()
  })
})

describe('ExportCsvButton', () => {
  it('downloads the filtered CSV and revokes the URL', async () => {
    vi.mocked(productService.exportProductsCsv).mockResolvedValue(new Blob(['a,b']))
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    render(<ExportCsvButton filters={{ ...DEFAULT_FILTERS, category: 'Kitchen' }} />)
    await userEvent.click(screen.getByRole('button', { name: 'Export CSV' }))
    await waitFor(() => expect(click).toHaveBeenCalled())
    expect(productService.exportProductsCsv).toHaveBeenCalledWith(
      expect.objectContaining({ category: 'Kitchen' }),
    )
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock')
    click.mockRestore()
  })

  it('shows a friendly error on failure', async () => {
    vi.mocked(productService.exportProductsCsv).mockRejectedValue(httpError(500))
    render(<ExportCsvButton filters={DEFAULT_FILTERS} />)
    await userEvent.click(screen.getByRole('button', { name: 'Export CSV' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not export')
  })
})

describe('AvatarUploader', () => {
  it('falls back to initials on 404 without showing an error', async () => {
    vi.mocked(uploadService.fetchAvatarBlob).mockRejectedValue(httpError(404))
    render(<AvatarUploader name="Ada Lovelace" />)
    expect(await screen.findByText('AL')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Remove avatar' })).not.toBeInTheDocument()
  })

  it('shows the image when one exists and rejects invalid uploads', async () => {
    vi.mocked(uploadService.fetchAvatarBlob).mockResolvedValue(new Blob(['x'], { type: 'image/png' }))
    render(<AvatarUploader name="Ada Lovelace" />)
    expect(await screen.findByAltText('Ada Lovelace avatar')).toHaveAttribute('src', 'blob:mock')
    await userEvent.upload(
      screen.getByLabelText('Upload avatar'),
      new File(['x'], 'a.gif', { type: 'image/gif' }),
      { applyAccept: false },
    )
    expect(await screen.findByRole('alert')).toHaveTextContent('PNG')
    expect(uploadService.uploadAvatar).not.toHaveBeenCalled()
  })
})
