// @vitest-environment jsdom
import { setImmediate as realImmediate } from 'node:timers';

import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DeliveryTab } from '@/features/projects/DeliveryTab';
import type { ClosureChecklist } from '@/features/projects/deliveryModel';

// @ts-expect-error plain ESM module without type declarations
import { deliveryRead } from '../mock/delivery-overview.mjs';

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const idOf = (v: string) => v;
let calls: Request[];
let respond: (url: URL, request: Request) => Response | Promise<Response>;
const mock = (url: URL) => {
  const r = deliveryRead({ pathname: url.pathname, idOf });
  return r ? json(r[0], r[1]) : json(404, { code: 'not_found', message: 'x' });
};

beforeEach(() => {
  calls = [];
  respond = mock;
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    calls.push(request);
    return respond(new URL(request.url), request);
  }));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function until(check: () => void, tries = 100) {
  for (let i = 0; ; i++) {
    try { check(); return; } catch (error) { if (i >= tries) throw error; }
    await act(async () => { await new Promise((r) => realImmediate(r)); });
  }
}
const paths = () => calls.map((c) => new URL(c.url).pathname);
const open = async (caseId = 'P-0101') => {
  render(<DeliveryTab caseId={caseId} />);
  await until(() => expect(screen.queryByText('Closure')).toBeTruthy());
};
const rows = () => screen.getAllByRole('listitem').filter((li) => li.classList.contains('delivery__row'));

describe('success', () => {
  it('reads the overview once, draws six rows in order and links Open to /work/{id}', async () => {
    await open();
    await until(() => expect(paths()).toContain('/api/v1/projects/P-0101/delivery/52/closure-checklist'));
    expect(paths().filter((p) => p.endsWith('/delivery-overview'))).toHaveLength(1);
    expect(rows().map((r) => r.querySelector('.delivery__title')!.textContent)).toEqual(['Release gates', 'Go-live acceptance', 'Hypercare', 'Handover to Support', 'Archive', 'Closure']);
    const release = within(rows()[0]);
    expect(release.getByText('REL-0091')).toBeTruthy();
    expect(release.getByText('VERIFIED')).toBeTruthy();
    expect(release.getByText('Updated 25 Mar')).toBeTruthy();
    expect(release.getByRole('link', { name: 'Open Release gates' }).getAttribute('href')).toBe('/work/2501');
    expect(within(rows()[3]).getByText('ACTION NEEDED')).toBeTruthy();
    const closure = within(rows()[5]);
    expect(closure.getByText('NOT STARTED')).toBeTruthy();
    expect(closure.queryByRole('link')).toBeNull();
    expect(screen.getByText(/^Checked /)).toBeTruthy();
  });

  const RULE = "Hypercare, archive and handover run side by side after go-live. Closure needs all of them, a saved retrospective and Finance's confirmation.";
  it('draws the board\'s static sentence under the rows at desktop width, with the board wording', async () => {
    await open();
    const note = screen.getByText("Hypercare, archive and handover run side by side after go-live. Closure needs all of them, a saved retrospective and Finance's confirmation.");
    expect(note.previousElementSibling!.tagName).toBe('OL');
  });

  it('hides the static sentence at phone width (SCR-43-mobile does not draw it)', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('max-width'), media: q, addEventListener: () => {}, removeEventListener: () => {} }));
    await open();
    expect(rows()).toHaveLength(6);
    expect(screen.queryByText(RULE)).toBeNull();
  });

  it('shows no counts, DLV number, gate wording or Tola text, and makes only GET requests', async () => {
    await open();
    await until(() => expect(paths()).toHaveLength(3));
    const text = document.body.textContent!;
    for (const banned of ['of 6 done', 'DLV-', 'RELEASE READY', 'Tola', 'Next']) expect(text).not.toContain(banned);
    expect(calls.every((c) => c.method === 'GET')).toBe(true);
  });

  it('lists only the held, unknown and unavailable checks under closure', async () => {
    await open();
    await until(() => expect(screen.getByText('Closure waits on:')).toBeTruthy());
    const reasons = within(rows()[5]).getAllByRole('listitem').map((li) => li.textContent);
    expect(reasons).toEqual(['Handover to Support Support listed 2 gaps.', 'Retrospective']);
    expect(rows()[5].textContent).not.toContain('Hypercare');
  });

  it('a project with nothing started shows six NOT STARTED rows, no link and no register read', async () => {
    await open('P-0102');
    expect(screen.getAllByText('NOT STARTED')).toHaveLength(6);
    expect(screen.queryAllByRole('link')).toHaveLength(0);
    expect(paths()).toEqual(['/api/v1/projects/P-0102/delivery-overview']);
  });
});

describe('closure reason reads', () => {
  const overviewWith = (closureWork: number | null, releaseWork: number | null) => {
    const body = deliveryRead({ pathname: '/api/v1/projects/P-0101/delivery-overview', idOf })[1];
    for (const l of body.lines) {
      if (l.key === 'delivery-closure/v1') { l.work_id = closureWork; l.work_url = closureWork ? `/work/${closureWork}` : null; }
      if (l.key === 'delivery-release/v1') { l.work_id = releaseWork; l.work_url = releaseWork ? `/work/${releaseWork}` : null; }
    }
    return body;
  };
  const ready: ClosureChecklist = { revision: 1, as_of: '2026-11-23T09:00:00Z', ready_to_prepare: true, recorded_closure_id: null, checks: [{ key: 'a', title: 'A', status: 'held', summary: 's', references: [], finding: null }], debt: null, retrospective_url: null };

  it('ready_to_prepare true shows no reason', async () => {
    respond = (url) => (url.pathname.endsWith('closure-checklist') ? json(200, ready) : mock(url));
    await open();
    await until(() => expect(paths().some((p) => p.endsWith('closure-checklist'))).toBe(true));
    await act(async () => { await new Promise((r) => realImmediate(r)); });
    expect(screen.queryByText('Closure waits on:')).toBeNull();
  });

  it.each([['release-register 403', 'release-register', 403], ['checklist 500', 'closure-checklist', 500]])('%s shows no reason and keeps the rows', async (_, tail, status) => {
    respond = (url) => (url.pathname.endsWith(tail) ? json(status, { code: 'x', message: 'secret' }) : mock(url));
    await open();
    await until(() => expect(paths().some((p) => p.endsWith(tail))).toBe(true));
    await act(async () => { await new Promise((r) => realImmediate(r)); });
    expect(rows()).toHaveLength(6);
    expect(screen.queryByText('Closure waits on:')).toBeNull();
    expect(document.body.textContent).not.toContain('secret');
  });

  it('a network failure on the register shows no reason and no banner', async () => {
    respond = (url) => { if (url.pathname.endsWith('release-register')) throw new TypeError('network'); return mock(url); };
    await open();
    await until(() => expect(paths().some((p) => p.endsWith('release-register'))).toBe(true));
    expect(rows()).toHaveLength(6);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('no checklist read when release has no work or closure has work', async () => {
    respond = (url) => (url.pathname.endsWith('delivery-overview') ? json(200, overviewWith(null, null)) : mock(url));
    await open();
    expect(paths()).toEqual(['/api/v1/projects/P-0101/delivery-overview']);
    cleanup();
    calls = [];
    respond = (url) => (url.pathname.endsWith('delivery-overview') ? json(200, overviewWith(2506, 2501)) : mock(url));
    await open();
    expect(paths()).toEqual(['/api/v1/projects/P-0101/delivery-overview']);
  });
});

describe('failure states', () => {
  it.each([403, 404])('%s shows the same no-access panel with nothing from the server', async (status) => {
    respond = () => json(status, { code: 'lagoon_secret', message: 'Lagoon Health secret' });
    render(<DeliveryTab caseId="P-0099" />);
    await until(() => expect(screen.getByRole('heading', { level: 1, name: 'You can’t open this project' })).toBeTruthy());
    expect(document.body.textContent).not.toContain('Lagoon');
  });

  it('a 500 shows the error panel and Try again re-reads once and recovers', async () => {
    let fail = true;
    respond = (url) => (fail ? json(500, { code: 'server_error', message: 'Lagoon boom' }) : mock(url));
    render(<DeliveryTab caseId="P-0101" />);
    await until(() => expect(screen.getByText('Delivery can’t be shown right now')).toBeTruthy());
    expect(document.body.textContent).not.toContain('Lagoon boom');
    const before = calls.length;
    fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(screen.getByText('Closure')).toBeTruthy());
    expect(paths().slice(before).filter((p) => p.endsWith('delivery-overview'))).toHaveLength(1);
  });

  it('a network failure shows the error panel', async () => {
    respond = () => { throw new TypeError('network'); };
    render(<DeliveryTab caseId="P-0101" />);
    await until(() => expect(screen.getByText('Delivery can’t be shown right now')).toBeTruthy());
  });

  it('a wrong-shaped answer shows the error panel, not a partial list', async () => {
    respond = () => json(200, { as_of: '2026-11-23T09:00:00Z', lines: [] });
    render(<DeliveryTab caseId="P-0101" />);
    await until(() => expect(screen.getByText('Delivery can’t be shown right now')).toBeTruthy());
    expect(screen.queryByText('Release gates')).toBeNull();
  });
});

describe('race', () => {
  it('a late answer for an earlier project is ignored', async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    respond = async (url) => {
      if (url.pathname.includes('P-0101')) { await gate; return mock(url); }
      return mock(url);
    };
    const view = render(<DeliveryTab caseId="P-0101" />);
    view.rerender(<DeliveryTab caseId="P-0102" />);
    await until(() => expect(screen.getAllByText('NOT STARTED')).toHaveLength(6));
    release();
    await act(async () => { await new Promise((r) => realImmediate(r)); });
    expect(screen.getAllByText('NOT STARTED')).toHaveLength(6);
    expect(screen.queryByText('REL-0091')).toBeNull();
  });
});
