// F-90: the invoice panel (key 'invoice', GET /projects/{case_id}/billing-invoices/{invoice_id}) on the live work item: one compact
// read-only block. A value the API returns as null is unknown: it reads "Unknown", never 0, and nothing is computed from the strings.
// No payment, correction or reminder control and no link to payments_url or corrections_url (the Finance workspaces own those).
import { ApiError } from '@/api/errors';
import type { LiveInvoice } from '@/api/types';
import { formatDayTime } from '@/components';

import { isPanelUrl, readPanel, registerLineAdapter, type LineAdapter } from './adapter';
import type { Section } from './labels';

export const UNKNOWN = 'Unknown';
const NOT_ISSUED = 'Not issued yet';
const NOT_DELIVERED = 'No delivery recorded';

/** The panel is omitted when its url is not the invoice route, or the server answers 404 or 403 for it. */
export type InvoiceReadback = LiveInvoice | null;

const INVOICE_URL = /^\/api\/v1\/projects\/[A-Za-z0-9_~-][A-Za-z0-9._~-]*\/billing-invoices\/\d+$/;

async function read(ref: { key: string; url: string }): Promise<InvoiceReadback> {
  if (!INVOICE_URL.test(ref.url) || !isPanelUrl(ref.url)) return null;
  try {
    return await readPanel<LiveInvoice>(ref);
  } catch (error) {
    if (error instanceof ApiError && (error.kind === 'not_found' || error.kind === 'forbidden')) return null;
    throw error;
  }
}

/** The server's own string with its currency; null stays Unknown. */
const money = (currency: string, value: string | null) => (value === null ? UNKNOWN : `${currency} ${value}`);

function sections(invoice: InvoiceReadback): Section[] {
  if (!invoice) return [];
  return [
    {
      key: 'invoice',
      kind: 'facts',
      title: 'Invoice',
      items: [
        { id: 'reference', label: 'Reference', value: invoice.reference },
        { id: 'version', label: 'Version', value: `v${invoice.version}` },
        { id: 'amount', label: 'Amount', value: money(invoice.currency, invoice.amount) },
        { id: 'issued', label: 'Issued', value: invoice.issued_at ? formatDayTime(invoice.issued_at) : NOT_ISSUED },
        { id: 'delivered', label: 'Delivered', value: invoice.delivered_at ? formatDayTime(invoice.delivered_at) : NOT_DELIVERED },
        { id: 'paid', label: 'Paid', value: money(invoice.currency, invoice.paid) },
        { id: 'owed', label: 'Owed', value: money(invoice.currency, invoice.owed) },
      ],
    },
  ];
}

export const invoiceAdapter: LineAdapter<InvoiceReadback> = { key: 'invoice', read, sections };

registerLineAdapter(invoiceAdapter as LineAdapter);
