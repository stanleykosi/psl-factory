// E-EXCEPTIONS types, derived from the generated contract (no edit to src/api).
import type { operations } from '@/api/schema';

type ContractPage = operations['E-EXCEPTIONS']['responses'][200]['content']['application/json'];
type ContractQuery = NonNullable<operations['E-EXCEPTIONS']['parameters']['query']>;

export type ExceptionKind = ContractPage['items'][number]['what'];
export type ExceptionsLimit = NonNullable<ContractQuery['limit']>;

// Engineering proposal (F-06, not yet in the contract): the SCR-10 boards draw a per-row reference, an open total,
// search and a kind filter. Each field is optional; the page draws nothing for a missing value.
/** One row; `ref` is the work's reference, e.g. "INV-0412". */
export type ExceptionRow = ContractPage['items'][number] & { ref?: string };
/** One page; `open_count` is every row matching the search and filter, across pages. */
export type ExceptionsPage = Omit<ContractPage, 'items'> & { items: ExceptionRow[]; open_count?: number };
/** Search text and one kind, sent as `q` and `what`. */
export type ExceptionsFilters = { q?: string; what?: ExceptionKind };
export type ExceptionsQuery = ContractQuery & ExceptionsFilters;
