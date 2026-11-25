// GET /api/v1/month-end (live contract 1.24.0, finance_operations_company_close). The page reads these fields and no others.
import type { operations } from '@/api/live-schema';

export type MonthEnd = operations['finance_operations_company_close']['responses'][200]['content']['application/json'];
export type MonthEndWork = MonthEnd['work'][number];
export type MonthEndCash = MonthEnd['cash'][number];
