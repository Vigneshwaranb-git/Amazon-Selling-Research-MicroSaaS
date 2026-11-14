import { motion } from 'framer-motion'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { OpportunityList } from '@/components/reviews/OpportunityList'
import { ProsConsList } from '@/components/reviews/ProsConsList'
import type { ReviewSummary } from '@/types/reviews'

interface SentimentSummaryProps {
  summary: ReviewSummary | null
  loading: boolean
  loadError: string | null
  analyzing: boolean
  analyzeError: string | null
  onAnalyze: () => void
  onRetry: () => void
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString()
}

export function SentimentSummary({
  summary,
  loading,
  loadError,
  analyzing,
  analyzeError,
  onAnalyze,
  onRetry,
}: SentimentSummaryProps) {
  const generated = summary ? formatDate(summary.generated_at) : ''
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
      <Card aria-label="AI review summary">
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-lg">AI review summary</CardTitle>
            <Button onClick={onAnalyze} disabled={analyzing || loading}>
              {analyzing ? 'Analyzing...' : summary ? 'Re-analyze' : 'Analyze reviews'}
            </Button>
          </div>
          {generated && <CardDescription>Generated {generated}</CardDescription>}
        </CardHeader>
        <CardContent className="space-y-4">
          {analyzeError && (
            <p role="alert" className="text-sm text-destructive">
              {analyzeError}
            </p>
          )}
          {loading && <p role="status">Loading summary...</p>}
          {loadError && (
            <div role="alert" className="space-y-2">
              <p className="text-sm text-destructive">{loadError}</p>
              <Button variant="outline" size="sm" onClick={onRetry}>
                Retry
              </Button>
            </div>
          )}
          {!loading && !loadError && !summary && (
            <p data-testid="summary-empty" className="text-sm text-muted-foreground">
              No AI summary yet. Analyze the reviews to see pros, cons and improvement opportunities.
            </p>
          )}
          {summary && (
            <div className="grid gap-6 md:grid-cols-3">
              <ProsConsList title="Pros" items={summary.pros} tone="pro" />
              <ProsConsList title="Cons" items={summary.cons} tone="con" />
              <OpportunityList items={summary.opportunities} />
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
