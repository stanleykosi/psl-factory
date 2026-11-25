// Words and rules for the client pages. Presentation only: billing that is unknown reads "Unknown", never "Set" and
// never "Missing"; an amount that is not known reads "Not known", never 0. Nothing here decides who may see a client.
import { formatClock, formatDayMonth } from '@/components';
import { plural } from '@/features/response/labels';

import type { Billing, DirectoryQuery, GroupRow, ProjectRow } from './api';

export const NOT_GIVEN = 'Not given';
export const BILLING_VALUES: readonly Billing[] = ['recorded', 'needed', 'unknown'];

/** "14 Nov, 10:00" (WAT), as the SCR-35 boards write it. */
export const asOfText = (value: string) => `${formatDayMonth(value)}, ${formatClock(value)}`;

/** `?billing=` is sent only when it is one of the three values; anything else is ignored. */
export const billingParam = (value: string | null | undefined): Billing | undefined => BILLING_VALUES.find((b) => b === value);

/** `?q=` trimmed, at most 100 characters (the contract's limit); blank is no search. */
export const searchParam = (value: string | null | undefined) => value?.trim().slice(0, 100) || undefined;

export const directoryQuery = (q: string | null | undefined, billing: string | null | undefined): DirectoryQuery => ({ q: searchParam(q), billing: billingParam(billing) });

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
/** A route id that looks like a case id is a workspace; anything else is a group key (the contract has no other discriminator). */
export const isCaseId = (value: string) => UUID.test(value);

export const clientPath = (id: string) => `/clients/${encodeURIComponent(id)}`;

/** The billing cell and tag of a group row: contacts_needed counts only the projects in the "needed" state. */
export const groupBilling = (row: GroupRow) =>
  row.contacts_needed > 0
    ? { needed: true, text: `${plural(row.contacts_needed, 'project')} ${row.contacts_needed === 1 ? 'needs' : 'need'} a billing contact`, tag: 'Billing contact missing' }
    : { needed: false, text: 'None needed', tag: 'None needed' };

export const projectBilling = (billing: Billing) =>
  billing === 'recorded'
    ? { state: billing, text: 'Set', tag: 'Set' }
    : billing === 'needed'
      ? { state: billing, text: 'Missing · invoices can’t start', tag: 'Billing contact missing' }
      : { state: billing, text: 'Unknown', tag: 'Unknown' };

/** The name a project row shows: the client when given, else the project title. */
export const projectName = (row: ProjectRow) => row.client ?? row.title;

/** "6 clients loaded as of 14 Nov, 10:00"; no total is returned, so it always says "loaded". The missing count waits for the last page. */
export function countLine(groups: GroupRow[], projects: ProjectRow[], complete: boolean, readAt: string) {
  const missing = groups.reduce((n, g) => n + g.contacts_needed, 0) + projects.filter((p) => p.billing === 'needed').length;
  const base = `${plural(groups.length + projects.length, 'client')} loaded as of ${asOfText(readAt)}`;
  return complete && missing > 0 ? `${base} · ${missing} missing billing contact` : base;
}

export const unknownProjectsText = (count: number) => `${plural(count, 'project')} with an amount not known`;
