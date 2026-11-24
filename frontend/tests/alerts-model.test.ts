import { describe, expect, it } from 'vitest';

import type { Alert, AlertPrefs } from '@/features/alerts/types';
import {
  agentName,
  alertHref,
  badgeText,
  bellName,
  buildPrefsBody,
  deliveryTime,
  deliveryWord,
  draftFrom,
  loadedLine,
  metaLine,
  needsYou,
  prefsChanged,
  subjectLine,
  summaryLine,
} from '@/features/alerts/model';

const alert = (patch: Partial<Alert> = {}): Alert => ({
  id: 'a'.repeat(64),
  title: 'Assistant reply',
  subject: 'Lagoon Health',
  detail: 'Tola',
  group: 'update',
  read: false,
  django_url: '/assistant/7/',
  at: '2026-11-23T09:58:00Z',
  agent: 'tola',
  target_kind: 'conversation',
  api_url: '/api/v1/assistant/conversations/7',
  ...patch,
});
// 10:42 WAT on 23 Nov 2026 (09:42Z).
const NOW = Date.parse('2026-11-23T09:42:00Z');

describe('meta line and secondary line', () => {
  it('gives the agent and the time when the alert has them', () => {
    expect(metaLine(alert(), NOW)).toBe('Tola · 10:58');
    expect(subjectLine(alert())).toBe('Lagoon Health · Tola');
  });

  it('shows neither agent nor time when both are null, and no placeholder', () => {
    expect(metaLine(alert({ agent: null, at: null }), NOW)).toBe('');
    expect(metaLine(alert({ at: null }), NOW)).toBe('Tola');
    expect(metaLine(alert({ agent: null }), NOW)).toBe('10:58');
  });

  it('an older WAT day reads "12 Nov"; the WAT day before reads "yesterday"; an unknown agent keeps its key', () => {
    expect(metaLine(alert({ at: '2026-11-12T08:00:00Z' }), NOW)).toBe('Tola · 12 Nov');
    // 23:30 WAT on 22 Nov is yesterday in Lagos, though it is 22:30Z.
    expect(metaLine(alert({ at: '2026-11-22T22:30:00Z' }), NOW)).toBe('Tola · yesterday');
    expect(agentName('kemi')).toBe('kemi');
    expect(metaLine(alert({ agent: 'kemi' }), NOW)).toBe('kemi · 10:58');
  });

  it('leaves out an empty subject or detail', () => {
    expect(subjectLine(alert({ subject: '', detail: 'INV-0398' }))).toBe('INV-0398');
    expect(subjectLine(alert({ subject: '', detail: ' ' }))).toBe('');
  });

  it('only the action group needs the person', () => {
    expect(needsYou(alert({ group: 'action' }))).toBe(true);
    expect(needsYou(alert({ group: 'update' }))).toBe(false);
  });
});

describe('alertHref (the typed link)', () => {
  const href = (api_url: string | null, django_url = '/accounts/profile/') => alertHref({ api_url, django_url });

  it('maps work, project and conversation api_url to the app routes', () => {
    expect(href('/api/v1/work/abc123')).toBe('/work/abc123');
    expect(href('/api/v1/work/4103')).toBe('/work/4103');
    expect(href('/api/v1/projects/6c2f1d3e-1a4b-4b8e-9d0a-0a1b2c3d4e5f')).toBe('/projects/6c2f1d3e-1a4b-4b8e-9d0a-0a1b2c3d4e5f');
    expect(href('/api/v1/assistant/conversations/7')).toBe('/assistant/7');
  });

  it('falls back to django_url /work/<id>/ when api_url is null or unrecognised', () => {
    expect(alertHref({ api_url: null, django_url: '/work/abc123/' })).toBe('/work/abc123');
    expect(alertHref({ api_url: '/api/v1/clients/9', django_url: '/work/abc123/' })).toBe('/work/abc123');
  });

  it('gives no link for null, absolute, protocol-relative, javascript:, multi-segment, dotted or empty values', () => {
    const refused = [
      null,
      '',
      'https://evil.example/api/v1/work/1',
      '//evil.example/api/v1/work/1',
      '/\\evil.example',
      'javascript:alert(1)',
      '/api/v1/work/',
      '/api/v1/work',
      '/api/v1/work/1/history',
      '/api/v1/work/a/b',
      '/api/v1/work/..',
      '/api/v1/work/.',
      '/api/v1/work/%2e%2e',
      '/api/v1/work/%2E%2E%2Fadmin',
      '/api/v1/work/a%2Fb',
      '/api/v1/work/a%5Cb',
      '/api/v1/work/a%00b%20c',
      '/api/v1/work/a b',
      '/api/v1/work/a?next=//evil',
      '/api/v1/work/a#x',
      '/api/v1/work/a.b',
      '/api/v1/work/%',
      '/API/V1/WORK/1',
      ' /api/v1/work/1',
      '/api/v1/work/1 ',
      '/api/v1/projects/%2e',
      '/api/v1/assistant/conversations/1/2',
      '/accounts/profile/',
    ];
    for (const value of refused) expect(href(value), String(value)).toBeUndefined();
  });

  it('refuses a django_url that is not exactly /work/<id>/', () => {
    for (const value of ['/work/abc123', '/work/abc/def/', '/work//', '/work/../', '/work/a.b/', '//work/1/', 'https://x.example/work/1/', '/accounts/login/', '/work/%2e%2e/', '/work/a%2Fb/', '', 'javascript:1']) {
      expect(alertHref({ api_url: null, django_url: value }), value).toBeUndefined();
    }
  });

  it('never returns anything but a single-slash same-origin path', () => {
    for (const value of ['/api/v1/work/abc', '/api/v1/projects/p-1', '/api/v1/assistant/conversations/3']) {
      expect(alertHref({ api_url: value, django_url: '' })).toMatch(/^\/[^/]/);
    }
  });
});

describe('badge and bell name', () => {
  it('hides the badge at 0 and when unknown, and reads 99+ above 99', () => {
    expect(badgeText(undefined)).toBeUndefined();
    expect(badgeText(0)).toBeUndefined();
    expect(badgeText(3)).toBe('3');
    expect(badgeText(99)).toBe('99');
    expect(badgeText(100)).toBe('99+');
    expect(badgeText(120)).toBe('99+');
  });

  it('names the bell with the unread total and the loaded need-you count', () => {
    expect(bellName(undefined, 0)).toBe('Alerts');
    expect(bellName(0, 0)).toBe('Alerts');
    expect(bellName(3, 0)).toBe('Alerts, 3 unread');
    expect(bellName(120, 2)).toBe('Alerts, 120 unread, 2 need you');
  });
});

describe('daily summary line', () => {
  const summary = { date: '2026-11-23', actions_open: 3, unread_updates_today: 2, unread_without_timestamp: 1, scope: 'current_inbox' as const };

  it('reads the three returned numbers', () => {
    expect(summaryLine(summary)).toBe('Today, 23 Nov: 3 need you, 2 new updates, 1 older unread.');
  });

  it('shows zero as 0 and a single update in the singular', () => {
    expect(summaryLine({ ...summary, actions_open: 0, unread_updates_today: 1, unread_without_timestamp: 0 })).toBe('Today, 23 Nov: 0 need you, 1 new update, 0 older unread.');
  });

  it('omits a part only when its field is missing, and says nothing without any', () => {
    expect(summaryLine({ ...summary, unread_updates_today: undefined })).toBe('Today, 23 Nov: 3 need you, 1 older unread.');
    expect(summaryLine({ date: '2026-11-23' })).toBeUndefined();
    expect(summaryLine(undefined)).toBeUndefined();
  });

  it('the loaded line never claims a total', () => {
    expect(loadedLine(25, 7)).toBe('25 loaded, 7 unread');
    expect(loadedLine(25, undefined)).toBe('25 loaded');
  });
});

describe('settings save body', () => {
  const prefs: AlertPrefs = {
    revision: 3,
    email_requested: true,
    whatsapp_requested: false,
    email_ready: true,
    whatsapp_ready: false,
    recent_deliveries: [],
  };

  it('sends exactly the revision and the two switches', () => {
    expect(buildPrefsBody(prefs, { email: true, whatsapp: true })).toEqual({ revision: 3, email_requested: true, whatsapp_requested: true });
    expect(Object.keys(buildPrefsBody(prefs, draftFrom(prefs))).sort()).toEqual(['email_requested', 'revision', 'whatsapp_requested']);
  });

  it('knows when nothing differs from what was read', () => {
    expect(prefsChanged(prefs, draftFrom(prefs))).toBe(false);
    expect(prefsChanged(prefs, { email: false, whatsapp: false })).toBe(true);
    expect(prefsChanged(prefs, { email: true, whatsapp: true })).toBe(true);
  });

  it('words the four receipt states; uncertain reads "Not confirmed"', () => {
    const states = ['queued', 'uncertain', 'delivered', 'held'] as const;
    expect(states.map(deliveryWord)).toEqual(['Queued', 'Not confirmed', 'Delivered', 'Held']);
    // "Delivered" only for the server state `delivered`, never for the others
    for (const state of states) expect(/deliver/i.test(deliveryWord(state)), state).toBe(state === 'delivered');
  });

  it('times a receipt by delivery, else by creation', () => {
    expect(deliveryTime({ channel: 'email', state: 'delivered', created_at: '2026-11-23T08:00:00Z', delivered_at: '2026-11-23T08:00:04Z', receipt: 'r' })).toBe('2026-11-23T08:00:04Z');
    expect(deliveryTime({ channel: 'whatsapp', state: 'uncertain', created_at: '2026-11-22T17:00:00Z', delivered_at: null, receipt: null })).toBe('2026-11-22T17:00:00Z');
  });
});
