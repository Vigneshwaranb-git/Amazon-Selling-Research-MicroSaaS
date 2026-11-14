import { useAsync, type AsyncState } from '@/hooks/useAsync'
import { fetchProduct, fetchProductHistory, fetchProducts } from '@/services/productService'
import type { ProductFilters, ProductHistory, ProductPage, TrackerProduct } from '@/types/products'

export function useProducts(filters: ProductFilters): AsyncState<ProductPage> {
  return useAsync(() => fetchProducts(filters), 'Could not load products. Please try again.', [
    filters.category,
    filters.min_margin,
    filters.max_saturation,
    filters.trend,
    filters.page,
  ])
}

export function useProduct(asin: string): AsyncState<TrackerProduct> {
  return useAsync(() => fetchProduct(asin), 'Could not load this product. Please try again.', [asin])
}

export function useProductHistory(asin: string): AsyncState<ProductHistory> {
  return useAsync(() => fetchProductHistory(asin), 'Could not load price history. Please try again.', [asin])
}
