'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';
import { DEFAULT_PAGE_SIZE, type PageSize } from '@/components';

import type { InvoiceList, InvoiceQuery } from './proposal';

export type PaymentsState = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'ready'; body: InvoiceList };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

function checked(data: InvoiceList) {
  if (!Array.isArray(data?.items) || typeof data.as_of !== 'string') throw new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);
  return data;
}

const fetchInvoices = (query: InvoiceQuery, limit: PageSize, cursor?: string): Promise<InvoiceList> =>
  call(api.GET('/api/v1/finance/invoices', { params: { query: { ...(query.q ? { q: query.q } : {}), ...(query.status ? { status: query.status } : {}), ...(cursor ? { cursor } : {}), limit } } }));

/** E-INVOICES: page 1 for the query in the address, then "Show more" appends the next page by the returned cursor.
 *  A changed query drops answers to the earlier one. Rows are shown as returned: nothing is filtered or counted here. */
export function usePayments(query: InvoiceQuery) {
  const [state, setState] = useState<PaymentsState>({ status: 'loading' });
  const [more, setMore] = useState<'idle' | 'loading' | 'error'>('idle');
  const seq = useRef(0);
  const pressed = useRef(false);
  const { q, status } = query;

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setState({ status: 'loading' });
    setMore('idle');
    try {
      const body = checked(await fetchInvoices({ q, status }, DEFAULT_PAGE_SIZE));
      if (mine === seq.current) setState({ status: 'ready', body });
    } catch (error) {
      if (mine === seq.current) setState({ status: 'error', error: asApiError(error) });
    }
  }, [q, status]);

  useEffect(() => {
    // The effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  /** Appends the next page; resolves with the number of rows before it, so the caller can move focus to the first new row. */
  const showMore = async (limit: PageSize) => {
    if (state.status !== 'ready' || !state.body.next_cursor || pressed.current) return undefined;
    pressed.current = true;
    const mine = seq.current;
    const before = state.body.items.length;
    setMore('loading');
    try {
      const page = checked(await fetchInvoices({ q, status }, limit, state.body.next_cursor));
      if (mine !== seq.current) return undefined;
      // the rows are appended; every other field (totals, note, count) stays as page 1 returned it
      setState((prev) => (prev.status !== 'ready' ? prev : { status: 'ready', body: { ...prev.body, items: [...prev.body.items, ...page.items], next_cursor: page.next_cursor } }));
      setMore('idle');
      return before;
    } catch (error) {
      if (mine !== seq.current) return undefined;
      const e = asApiError(error);
      if (e.kind === 'unauthenticated') setState({ status: 'error', error: e });
      else setMore('error');
      return undefined;
    } finally {
      pressed.current = false;
    }
  };

  return { state, more, retry: load, showMore };
}
