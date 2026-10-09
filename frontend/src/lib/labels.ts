import type { Category } from '../types/api'

export const CATEGORY_LABEL: Record<Category, string> = {
  invoice: 'Invoice',
  receipt: 'Receipt',
  other: 'Other',
  uncertain: 'Uncertain',
}
