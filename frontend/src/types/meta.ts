export type DataProvider = 'mock' | 'dataset'

export interface DataSourceInfo {
  provider: DataProvider
  attribution: string | null
  data_as_of: string | null
  notes: string[]
}
