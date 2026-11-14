import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface ReviewFiltersProps {
  rating: number
  keyword: string
  onRatingChange: (rating: number) => void
  onKeywordChange: (keyword: string) => void
  onReset: () => void
}

export function ReviewFilters({ rating, keyword, onRatingChange, onKeywordChange, onReset }: ReviewFiltersProps) {
  return (
    <form
      className="flex flex-wrap items-end gap-3"
      aria-label="Review filters"
      onSubmit={(e) => e.preventDefault()}
    >
      <label className="flex flex-col gap-1 text-xs">
        Star rating
        <select
          className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          value={rating}
          onChange={(e) => onRatingChange(Number(e.target.value))}
        >
          <option value={0}>All ratings</option>
          {[5, 4, 3, 2, 1].map((r) => (
            <option key={r} value={r}>
              {r} {r === 1 ? 'star' : 'stars'}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs">
        Keyword
        <Input value={keyword} onChange={(e) => onKeywordChange(e.target.value)} placeholder="e.g. battery" />
      </label>
      <Button type="button" variant="outline" onClick={onReset}>
        Reset
      </Button>
    </form>
  )
}
