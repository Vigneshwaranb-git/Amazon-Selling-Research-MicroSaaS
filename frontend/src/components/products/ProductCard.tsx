import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { Minus, TrendingDown, TrendingUp } from 'lucide-react'
import type { TrackerProduct } from '@/types/products'

interface ProductCardProps {
  product: TrackerProduct
}

const fmt = (n: number | null | undefined, prefix = ''): string =>
  n === null || n === undefined ? '-' : `${prefix}${n.toLocaleString('en-US')}`

export function ProductCard({ product }: ProductCardProps) {
  const TrendIcon =
    product.trend === 'rising' ? TrendingUp : product.trend === 'declining' ? TrendingDown : Minus
  return (
    <motion.article
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4 }}
      className="rounded-2xl border bg-card p-4 shadow-sm"
    >
      <Link to={`/products/${product.asin}`} className="block">
        <h3 className="line-clamp-2 font-semibold">{product.title}</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          {product.asin} {product.category ? `· ${product.category}` : ''}
        </p>
      </Link>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
        <div>
          <dt className="text-xs text-muted-foreground">Price</dt>
          <dd>{fmt(product.price, '$')}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">BSR</dt>
          <dd>{fmt(product.current_bsr, '#')}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Monthly sales</dt>
          <dd>{fmt(product.estimated_monthly_sales)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Margin</dt>
          <dd>{product.estimated_margin == null ? '-' : `${product.estimated_margin}%`}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Saturation</dt>
          <dd>{fmt(product.saturation_score)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Trend</dt>
          <dd className="flex items-center gap-1 capitalize">
            <TrendIcon className="size-4" aria-hidden="true" />
            {product.trend ?? 'n/a'}
          </dd>
        </div>
      </dl>
    </motion.article>
  )
}
