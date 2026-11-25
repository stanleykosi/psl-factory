// GET /api/v1/payments (live contract 1.24.0, finance_operations_payments). The page reads these fields and no others.
import type { operations } from '@/api/live-schema';

export type InvoiceList = operations['finance_operations_payments']['responses'][200]['content']['application/json'];
export type InvoiceRow = InvoiceList['items'][number];
export type InvoiceTotal = InvoiceList['totals'][number];
export type InvoiceQuery = { q?: string; status?: string };
