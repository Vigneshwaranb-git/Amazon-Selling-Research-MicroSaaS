import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { DEFAULT_FILTERS, type ProductFilters, type Trend } from '@/types/products'

interface FilterBarProps {
  filters: ProductFilters
  onChange: (filters: ProductFilters) => void
}

// The API filters on a minimum trend score, so only "rising" can be requested.
const TRENDS: Trend[] = ['rising']

export function FilterBar({ filters, onChange }: FilterBarProps) {
  const update = (patch: Partial<ProductFilters>) => onChange({ ...filters, ...patch, page: 1 })
  return (
    <form
      className="flex flex-wrap items-end gap-3"
      aria-label="Product filters"
      onSubmit={(e) => e.preventDefault()}
    >
      <label className="flex flex-col gap-1 text-xs">
        Category
        <Input
          value={filters.category}
          onChange={(e) => update({ category: e.target.value })}
          placeholder="e.g. Kitchen"
        />
      </label>
      <label className="flex flex-col gap-1 text-xs">
        Min margin %
        <Input
          type="number"
          min={0}
          value={filters.min_margin}
          onChange={(e) => update({ min_margin: e.target.value })}
        />
      </label>
      <label className="flex flex-col gap-1 text-xs">
        Max saturation
        <Input
          type="number"
          min={0}
          value={filters.max_saturation}
          onChange={(e) => update({ max_saturation: e.target.value })}
        />
      </label>
      <label className="flex flex-col gap-1 text-xs">
        Trend
        <select
          className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          value={filters.trend}
          onChange={(e) => update({ trend: e.target.value as Trend | '' })}
        >
          <option value="">Any</option>
          {TRENDS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>
      <Button type="button" variant="outline" onClick={() => onChange(DEFAULT_FILTERS)}>
        Reset
      </Button>
    </form>
  )
}
