import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import type { Alert, AlertPrefs } from '@/features/alerts/types';
import {
  agentImage,
  agentName,
  buildAlertQuery,
  buildPrefsBody,
  countLine,
  deliveryWords,
  draftFrom,
  filterCount,
  metaLine,
  parseView,
  quietLabel,
  viewSearch,
} from '@/features/alerts/model';

const fixture = (name: string) => JSON.parse(readFileSync(join(__dirname, '../mock/fixtures', name), 'utf8'));
const board = fixture('E-NOTIFICATIONS.json') as { items: Alert[]; as_of: string };
const prefs = fixture('E-ALERT-PREFS-READ.json') as AlertPrefs;
// 11:00 WAT on the board's day (as_of).
const NOW = Date.parse(board.as_of);

describe('meta line (SCR-15 presentation rules)', () => {
  it('gives each board line', () => {
    expect(board.items.map((a) => metaLine(a, NOW))).toEqual([
      'Chidi · WhatsApp and email · 10:42',
      'Tola · Email · 09:00 daily digest',
      'Zainab · In app only (you are not HR)',
      'Chidi · In app · yesterday',
    ]);
  });

  it('with every proposal field absent: agent and the base time only', () => {
    const { id, work_id, agent, text, at, read } = board.items[0];
    expect(metaLine({ id, work_id, agent, text, at, read }, NOW)).toBe('Chidi · 10:42');
  });

  it('orders channels whatsapp, email, in app and capitalises the first word', () => {
    expect(deliveryWords(['in_app', 'email'])).toBe('Email and in app');
    expect(deliveryWords(['email', 'whatsapp'])).toBe('WhatsApp and email');
    expect(deliveryWords(['in_app'])).toBe('In app');
  });

  it('an older WAT day reads "12 Nov"; the WAT day before reads "yesterday"', () => {
    const base = board.items[3];
    expect(metaLine({ ...base, delivered_at: '2026-11-12T08:00:00Z' }, NOW)).toBe('Chidi · In app · 12 Nov');
    // 23:30 WAT on 13 Nov is still yesterday in Lagos, though it is 22:30Z.
    expect(metaLine({ ...base, delivered_at: '2026-11-13T22:30:00Z' }, NOW)).toBe('Chidi · In app · yesterday');
    // 00:30 WAT on 14 Nov is today in Lagos, though it is still 13 Nov in UTC.
    expect(metaLine({ ...base, delivered_at: '2026-11-13T23:30:00Z' }, NOW)).toBe('Chidi · In app · 00:30');
  });

  it('an unknown agent keeps its key as the name and gets no image', () => {
    expect(agentName('kemi')).toBe('kemi');
    expect(agentImage('kemi')).toBeUndefined();
    expect(metaLine({ ...board.items[0], agent: 'kemi' }, NOW)).toBe('kemi · WhatsApp and email · 10:42');
    expect(['tola', 'chidi', 'zainab'].map(agentImage)).toEqual(['/agents/tola.png', '/agents/chidi.png', '/agents/zainab.png']);
  });
});

describe('count line', () => {
  it('reads "1 ALERT", "0 ALERTS" and "4 ALERTS" from total, and nothing without total', () => {
    expect(countLine(1)).toBe('1 ALERT');
    expect(countLine(0)).toBe('0 ALERTS');
    expect(countLine(4)).toBe('4 ALERTS');
    expect(countLine(undefined)).toBeUndefined();
  });
});

describe('list view in the URL', () => {
  it('reads q, a known agent and unread=1; ignores unknown values', () => {
    expect(parseView(new URLSearchParams('q=payroll&agent=chidi&unread=1'))).toEqual({ q: 'payroll', agent: 'chidi', unread: true });
    expect(parseView(new URLSearchParams('q=&agent=kemi&unread=yes'))).toEqual({});
  });

  it('writes empty values out of the URL', () => {
    expect(viewSearch({})).toBe('');
    expect(viewSearch({ q: 'payroll', unread: true })).toBe('?q=payroll&unread=1');
  });

  it('sends only q, agent, unread=true and cursor; never limit', () => {
    expect(buildAlertQuery({})).toEqual({});
    expect(buildAlertQuery({ q: 'x', agent: 'tola', unread: true }, 'o20')).toEqual({ q: 'x', agent: 'tola', unread: true, cursor: 'o20' });
    expect(filterCount({ q: 'x' })).toBe(0);
    expect(filterCount({ agent: 'tola', unread: true })).toBe(2);
  });
});

describe('settings PUT body', () => {
  it('echoes channel, frequency and revision, sends every event in order, digest and quiet hours on desktop', () => {
    const draft = draftFrom(prefs);
    expect(buildPrefsBody(prefs, draft, false)).toEqual({
      channel: 'both',
      frequency: 'immediate',
      expected_revision: 3,
      events: prefs.events.map(({ key, whatsapp, email }) => ({ key, whatsapp, email })),
      digest_at: '08:00',
      quiet_hours: '20-07-weekends',
    });
  });

  it('the phone sends no digest_at and no quiet_hours', () => {
    const body = buildPrefsBody(prefs, draftFrom(prefs), true);
    expect(body).not.toHaveProperty('digest_at');
    expect(body).not.toHaveProperty('quiet_hours');
  });

  it('omits expected_revision when none was read, and never remaps an unknown channel', () => {
    const { revision: _revision, ...v6 } = prefs;
    void _revision;
    const odd = { ...(v6 as AlertPrefs), channel: 'sms' };
    const body = buildPrefsBody(odd, draftFrom(odd), false);
    expect(body).not.toHaveProperty('expected_revision');
    expect(body.channel).toBe('sms');
  });

  it('a select left on "Not set" is not sent; quiet hours read as the chosen label', () => {
    const unset = { ...prefs, digest_at: { options: prefs.digest_at!.options } };
    expect(buildPrefsBody(unset, draftFrom(unset), false)).not.toHaveProperty('digest_at');
    expect(quietLabel(prefs)).toBe('20:00 to 07:00, and weekends');
    expect(quietLabel({ ...prefs, quiet_hours: { options: prefs.quiet_hours!.options } })).toBeUndefined();
  });
});
