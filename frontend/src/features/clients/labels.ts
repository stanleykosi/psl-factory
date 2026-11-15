// Words for the client pages. Presentation only: an amount that is not known reads "Unknown", never 0; nothing here
// decides who may change a client or whether an invoice may start.
import { formatDateTime } from '@/components';
import { plural } from '@/features/response/labels';

import type { ClientRow } from './api';

export const UNKNOWN = 'Unknown';
export const NOT_GIVEN = 'Not given';

/** "14 Nov 2026 10:00 WAT". */
export const asOfText = (value: string) => formatDateTime(value);

/** "6 clients as of 14 Nov, 10:00"; with more pages to load it says "loaded", because no total is returned. */
export function countLine(rows: ClientRow[], complete: boolean, asOf: string) {
  const missing = rows.filter((row) => !row.billing_contact_set).length;
  const base = `${plural(rows.length, 'client')}${complete ? '' : ' loaded'} as of ${asOfText(asOf)}`;
  return complete && missing > 0 ? `${base} · ${missing} missing billing contact` : base;
}

export const clientPath = (clientId: string) => `/clients/${encodeURIComponent(clientId)}`;
