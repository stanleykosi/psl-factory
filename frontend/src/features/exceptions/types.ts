// E-EXCEPTIONS types, derived from the generated contract (no edit to src/api).
import type { operations } from '@/api/schema';

export type ExceptionsPage = operations['E-EXCEPTIONS']['responses'][200]['content']['application/json'];
export type ExceptionRow = ExceptionsPage['items'][number];
export type ExceptionKind = ExceptionRow['what'];
export type ExceptionsLimit = NonNullable<NonNullable<operations['E-EXCEPTIONS']['parameters']['query']>['limit']>;
