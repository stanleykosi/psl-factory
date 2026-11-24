// Shared by the alerts component tests (F-61): live-shaped alert items and bodies, and the fetch stub's helpers.
import { setImmediate as realImmediate } from 'node:timers';

import { act } from '@testing-library/react';

import type { Alert } from '@/features/alerts/types';

export const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

export async function until(check: () => void, tries = 100) {
  for (let i = 0; ; i++) {
    try {
      check();
      return;
    } catch (error) {
      if (i >= tries) throw error;
    }
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
  }
}

export const settle = () =>
  act(async () => {
    await new Promise((r) => realImmediate(r));
  });

export const hex = (n: number | string) => String(n).padStart(64, '0');

/** A live item; fixed past times so "12 Nov" does not depend on the day the tests run. */
export const alert = (patch: Partial<Alert> & { n?: number } = {}): Alert => {
  const { n = 1, ...rest } = patch;
  return {
    id: hex(n),
    title: `Invoice review ${n}`,
    subject: 'Ojo Foods',
    detail: `INV-${String(n).padStart(4, '0')}`,
    group: 'update',
    read: false,
    django_url: `/work/${n}/`,
    at: '2026-11-12T08:30:00Z',
    agent: 'chidi',
    target_kind: 'work',
    api_url: `/api/v1/work/${n}`,
    ...rest,
  };
};

const SUMMARY = { date: '2026-11-23', actions_open: 3, unread_updates_today: 2, unread_without_timestamp: 1, scope: 'current_inbox' as const };

/** A page-1 body; `unread` counts the whole inbox. */
export const body = (items: Alert[], patch: Record<string, unknown> = {}) => ({
  items,
  as_of: '2026-11-23T10:42:00Z',
  page: 1,
  next_page: null,
  unread: items.filter((item) => !item.read).length,
  daily_summary: SUMMARY,
  ...patch,
});
