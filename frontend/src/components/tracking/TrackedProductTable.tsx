import { Link } from 'react-router-dom'
import { Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { Product } from '@/types'

interface Props {
  products: Product[]
  onRemove: (asin: string) => void
}

export function TrackedProductTable({ products, onRemove }: Props) {
  if (products.length === 0) {
    return <p className="p-4 text-sm text-muted-foreground">No products in this list yet.</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr>
            <th className="p-2">Product</th>
            <th className="p-2">Price</th>
            <th className="p-2">BSR</th>
            <th className="p-2">Monthly sales</th>
            <th className="p-2">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {products.map((p) => (
            <tr key={p.asin} className="border-t">
              <td className="p-2">
                <Link className="hover:underline" to={`/products/${p.asin}`}>
                  {p.title}
                </Link>
              </td>
              <td className="p-2">{p.price === null ? '-' : `$${p.price}`}</td>
              <td className="p-2">
                {p.current_bsr === null ? '-' : `#${p.current_bsr.toLocaleString('en-US')}`}
              </td>
              <td className="p-2">{p.estimated_monthly_sales?.toLocaleString('en-US') ?? '-'}</td>
              <td className="p-2">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove ${p.title}`}
                  onClick={() => onRemove(p.asin)}
                >
                  <Trash2 className="size-4" />
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
