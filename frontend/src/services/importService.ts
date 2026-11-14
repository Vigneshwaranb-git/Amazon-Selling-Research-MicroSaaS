import api from '@/services/api'

export interface ImportRowError {
  row: number
  message: string
}

export interface AsinImportResult {
  added: number
  skipped: number
  errors: ImportRowError[]
}

export interface CostSheetImportResult {
  created: number
  errors: ImportRowError[]
}

/** Target of an ASIN import: exactly one of an existing list or a new list name. */
export type AsinImportTarget = { trackingListId: number } | { newListName: string }

function csvForm(file: File): FormData {
  const form = new FormData()
  form.append('file', file)
  return form
}

export async function importAsins(file: File, target: AsinImportTarget): Promise<AsinImportResult> {
  const params =
    'trackingListId' in target
      ? { tracking_list_id: target.trackingListId }
      : { new_list_name: target.newListName }
  const { data } = await api.post<AsinImportResult>('/imports/asins', csvForm(file), { params })
  return data
}

export async function importCostSheet(file: File): Promise<CostSheetImportResult> {
  const { data } = await api.post<CostSheetImportResult>('/imports/cost-sheet', csvForm(file))
  return data
}
