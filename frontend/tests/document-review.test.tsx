// @vitest-environment jsdom
// F-29: the document review page (SCR-08) against a fetch stub that stands in for the contract mock. The fields beyond
// the typed E-DOCUMENT ones are proposals; nothing here proves a backend.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DocumentReviewPage } from '@/features/documents/DocumentReview';
import { AppShell } from '@/shell/AppShell';
import { bellFeed, isBellFeed } from './bell-feed';

configure({ asyncUtilTimeout: 4000 });

const nav = vi.hoisted(() => ({ search: 'v=2' }));
vi.mock('next/navigation', () => ({
  usePathname: () => '/projects/P-0101/documents/D-2901',
  useSearchParams: () => new URLSearchParams(nav.search),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = <T,>(name: string): T => JSON.parse(readFileSync(join(fixtures, name), 'utf8')) as T;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
type Doc = Record<string, unknown> & { sections?: Record<string, unknown>[]; review?: Record<string, unknown>; checks?: Record<string, unknown>[] };
const docV2 = (): Doc => read('documents/D-2901.2.json');
const work = (name: string) => read<{ tasks: { id: string; revision: number }[] }>(`work/${name}.json`);

type Call = { method: string; path: string; body: Record<string, unknown> | undefined };
let calls: Call[];
let docAnswers: (() => Response)[];
let workAnswers: (() => Response)[];
let writes: { claim: () => Response; decide: () => Response };

const gets = (prefix: string) => calls.filter((c) => c.method === 'GET' && c.path.startsWith(prefix));
const posts = (suffix: string) => calls.filter((c) => c.method === 'POST' && c.path.endsWith(suffix));
const next = (list: (() => Response)[]) => (list.length > 1 ? list.shift()! : list[0])();

beforeEach(() => {
  nav.search = 'v=2';
  calls = [];
  docAnswers = [() => json(200, docV2())];
  workAnswers = [() => json(200, work('W-2901'))];
  writes = {
    claim: () => json(200, { task_id: 'T-2901', revision: 2, claimed_by: 'Tunde Bello' }),
    decide: () => json(200, { task_id: 'T-2901', verdict: 'approve', decided_by: 'Tunde Bello', decided_at: '2026-11-17T09:05:00Z', work_state: 'processing' }),
  };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
      const url = new URL(request.url);
      const text = request.method === 'GET' ? '' : await request.clone().text();
      calls.push({ method: request.method, path: url.pathname, body: text ? JSON.parse(text) : undefined });
      if (url.pathname === '/api/v1/me') return json(200, read('me.pm.json'));
      if (url.pathname === '/api/v1/projects/P-0101') return json(200, read('projects/P-0101.json'));
      if (url.pathname.startsWith('/api/v1/documents/')) return next(docAnswers);
      if (url.pathname.endsWith('/claim')) return writes.claim();
      if (url.pathname.endsWith('/decision')) return writes.decide();
      if (url.pathname.startsWith('/api/v1/work/')) return next(workAnswers);
      return json(404, { code: 'not_found', message: 'Not here.' });
    }),
  );
});
afterEach(() => vi.unstubAllGlobals());

async function open() {
  render(
    <AppShell>
      <DocumentReviewPage caseId="P-0101" documentId="D-2901" />
    </AppShell>,
  );
}
const heading = () => screen.findByRole('heading', { level: 1, name: /Statement of work/ });
const banner = () => document.querySelector('.docrev__returnedhead')?.textContent;
const buttons = () => screen.queryAllByRole('button').map((b) => b.textContent);

describe('the review page as the acting reviewer', () => {
  it('shows the sections, the agent note, the checks, the audience and the two buttons', async () => {
    await open();
    expect((await heading()).textContent).toBe('Statement of work · v2');
    expect(screen.getByText('Awaiting PMO Lead review')).toBeTruthy();
    const sections = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent);
    expect(sections).toEqual(['1. Scope', '2. Deliverables', '3. Milestones and stages', '4. Assumptions', '5. Out of scope']);
    expect(screen.getByText(/the minutes say "week 3"/)).toBeTruthy();
    expect(await screen.findByText(/Changes since v1: Section 3/)).toBeTruthy();
    expect(screen.getByText('Matches COST-0140 v2')).toBeTruthy();
    expect(screen.getByText('5 of 5')).toBeTruthy();
    expect(screen.getByText('Client · Lagoon Health')).toBeTruthy();
    expect(screen.getByText('TEST TEMPLATE')).toBeTruthy();
    expect(await screen.findByRole('button', { name: 'Approve v2' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Return with note' })).toBeTruthy();
    expect(screen.getByLabelText('Note for the PM (needed to return)')).toBeTruthy();
    expect(screen.getByText('Approving records your name and time. Approving does not send it to the client.')).toBeTruthy();
  });

  it('approve claims once, decides once with the read revision and no note, then shows the re-read result', async () => {
    await open();
    await screen.findByRole('button', { name: 'Approve v2' });
    await waitFor(() => expect(posts('/claim')).toHaveLength(1));
    docAnswers = [() => json(200, { ...docV2(), status: 'Approved' })];
    workAnswers = [() => json(200, work('W-2901.approve'))];
    await waitFor(() => expect((screen.getByRole('button', { name: 'Approve v2' }) as HTMLButtonElement).disabled).toBe(false));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Approve v2' }));
    });
    await screen.findByText(/You approved v2/);
    expect(posts('/decision')).toHaveLength(1);
    expect(posts('/decision')[0].body).toEqual({ expected_revision: 2, verdict: 'approve' });
    expect(posts('/claim')).toHaveLength(1);
    expect(screen.getByRole('status').textContent).toBe('You approved v2 · Kemi Adebayo · 17 Nov 10:05. Not sent to the client.');
    expect(screen.queryByRole('button', { name: 'Approve v2' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Return with note' })).toBeNull();
    expect(gets('/api/v1/documents/').length).toBeGreaterThanOrEqual(2);
  });

  it('return with an empty note sends nothing and says why; with a note it sends the verdict and shows the returned state', async () => {
    await open();
    const ret = await screen.findByRole('button', { name: 'Return with note' });
    await waitFor(() => expect((ret as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(ret);
    expect(await screen.findByText('Add a note to return it.')).toBeTruthy();
    expect(posts('/decision')).toHaveLength(0);

    const returned = { ...docV2(), status: 'Returned to PM', returned: { by: 'Kemi Adebayo', role: 'PMO Lead', at: '2026-11-17T13:20:00Z', note: 'Section 4: confirm week 2 or 3.' } };
    docAnswers = [() => json(200, returned)];
    workAnswers = [() => json(200, work('W-2901.return'))];
    writes.decide = () => json(200, { task_id: 'T-2901', verdict: 'return', decided_by: 'Tunde Bello', decided_at: '2026-11-17T13:20:00Z', work_state: 'action_needed' });
    fireEvent.change(screen.getByLabelText('Note for the PM (needed to return)'), { target: { value: 'Section 4: confirm week 2 or 3.' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Return with note' }));
    });
    await waitFor(() => expect(banner()).toBe('Returned by Kemi Adebayo (PMO Lead) · 17 Nov 14:20'));
    expect(posts('/decision')[0].body).toEqual({ expected_revision: 2, verdict: 'return', note: 'Section 4: confirm week 2 or 3.' });
    expect(screen.getByText('“Section 4: confirm week 2 or 3.”')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Approve v2' })).toBeNull();
  });

  it('a 409 on the decision says so, re-reads and sends no second decision', async () => {
    await open();
    await waitFor(() => expect((screen.getByRole('button', { name: 'Approve v2' }) as HTMLButtonElement).disabled).toBe(false));
    writes.decide = () => json(409, { code: 'stale_revision', message: 'Someone changed this.' });
    workAnswers = [() => json(200, { ...work('W-2901'), revision: 7 })];
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Approve v2' }));
    });
    await screen.findByText(/changed while you were reading it/);
    expect(posts('/decision')).toHaveLength(1);
    expect(screen.queryByText(/You approved/)).toBeNull();
  });

  it('a server error after the write shows no approval, re-reads the item and does not resend', async () => {
    await open();
    await waitFor(() => expect((screen.getByRole('button', { name: 'Approve v2' }) as HTMLButtonElement).disabled).toBe(false));
    writes.decide = () => json(500, { code: 'server_error', message: 'Oops.' });
    const before = gets('/api/v1/work/').length;
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Approve v2' }));
    });
    await screen.findByText(/couldn’t confirm your decision/);
    expect(screen.queryByText(/You approved/)).toBeNull();
    expect(posts('/decision')).toHaveLength(1);
    expect(gets('/api/v1/work/').length).toBeGreaterThan(before);
  });
});

describe('who may act', () => {
  it('a reviewer who prepared it has no controls and reads why', async () => {
    docAnswers = [() => json(200, { ...docV2(), review: { role_label: 'PMO Lead', work_id: 'W-2902', task_id: 'T-2902' } })];
    workAnswers = [() => json(200, work('W-2902'))];
    await open();
    await heading();
    await screen.findByText(/You prepared Statement of work v2, so someone else must review it\./);
    expect(buttons().filter((b) => /Approve|Return/.test(b ?? ''))).toEqual([]);
    expect(screen.queryByLabelText('Note for the PM (needed to return)')).toBeNull();
    expect(posts('/claim')).toHaveLength(0);
  });

  it('with no review task the page is read-only and sends no claim or decision', async () => {
    docAnswers = [() => json(200, { ...docV2(), review: { role_label: 'PMO Lead' } })];
    await open();
    await heading();
    await screen.findByText('This review isn’t open to you here.');
    expect(buttons().filter((b) => /Approve|Return/.test(b ?? ''))).toEqual([]);
    expect(calls.filter((c) => c.method === 'POST')).toEqual([]);
    expect(gets('/api/v1/work/')).toHaveLength(0);
  });
});

describe('what the page shows of the response', () => {
  it('shows tags and text as plain characters, never markup', async () => {
    const hostile = docV2();
    hostile.sections![0] = { key: 'scope', heading: 'Scope <b>bold</b>', text: 'Plain <script>alert(1)</script> text', notes: [{ agent: 'tola', text: '<b>note</b>' }] };
    docAnswers = [() => json(200, hostile)];
    await open();
    await heading();
    expect(screen.getByText('Plain <script>alert(1)</script> text')).toBeTruthy();
    expect(screen.getByText(/1\. Scope <b>bold<\/b>/)).toBeTruthy();
    expect(document.querySelector('main script, article script, article b')).toBeNull();
  });

  it('an unknown amounts check reads Unknown, never Matches', async () => {
    const doc = docV2();
    doc.checks = doc.checks!.map((c) => (c.key === 'amounts' ? { key: 'amounts', label: c.label, status: 'unknown', detail: 'The costing figure is not available.' } : c));
    docAnswers = [() => json(200, doc)];
    await open();
    await heading();
    expect(screen.queryByText(/Matches/)).toBeNull();
    const row = screen.getByText('Amounts match approved costing').closest('li')!;
    expect(within(row).getByText('Unknown')).toBeTruthy();
    expect(within(row).getByText('The costing figure is not available.')).toBeTruthy();
  });

  it('no sections field gives the download link and the sentence; an empty list gives the empty sentence', async () => {
    const noSections = docV2();
    delete noSections.sections;
    docAnswers = [() => json(200, noSections)];
    await open();
    await heading();
    expect(screen.getByText('The text isn’t available here.')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Download' }).getAttribute('href')).toBe('https://files.example.test/sow-d-2901-v2.pdf');
  });

  it('a body_url that is not http(s) or relative is not a link', async () => {
    const doc = { ...docV2(), body_url: 'javascript:alert(1)' };
    delete doc.sections;
    docAnswers = [() => json(200, doc)];
    await open();
    await heading();
    expect(screen.getByText('The text isn’t available here.')).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Download' })).toBeNull();
  });

  it('a return the re-read does not show says so instead of recording forever', async () => {
    await open();
    const ret = await screen.findByRole('button', { name: 'Return with note' });
    await waitFor(() => expect((ret as HTMLButtonElement).disabled).toBe(false));
    fireEvent.change(screen.getByLabelText('Note for the PM (needed to return)'), { target: { value: 'Fix it' } });
    writes.decide = () => json(200, { task_id: 'T-2901', verdict: 'return', decided_by: 'Tunde Bello', decided_at: '2026-11-17T13:20:00Z', work_state: 'action_needed' });
    workAnswers = [() => json(200, work('W-2901.return'))];
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Return with note' }));
    });
    await screen.findByText(/couldn’t confirm the return was recorded/);
    expect(screen.queryByText('Recording the return…')).toBeNull();
    expect(posts('/decision')).toHaveLength(1);
  });

  it('the returned state quotes the note only where it is sent', async () => {
    const returned = { ...docV2(), status: 'Returned to PM', returned: { by: 'Kemi Adebayo', role: 'PMO Lead', at: '2026-11-17T13:20:00Z' } };
    docAnswers = [() => json(200, returned)];
    await open();
    await heading();
    expect(banner()).toBe('Returned by Kemi Adebayo (PMO Lead) · 17 Nov 14:20');
    expect(screen.getByText('The note isn’t shown to you.')).toBeTruthy();
    expect(screen.getByText(/Approval on v2 is not carried over\./)).toBeTruthy();
    expect(document.querySelector('.docrev__quote')?.textContent).toBe('The note isn’t shown to you.');
  });

  it('the held buttons are disabled, say why and send nothing', async () => {
    const returned = { ...docV2(), status: 'Returned to PM', returned: { by: 'Kemi Adebayo', role: 'PMO Lead', at: '2026-11-17T13:20:00Z', note: 'x' } };
    docAnswers = [() => json(200, returned)];
    await open();
    await heading();
    await screen.findByRole('button', { name: /Edit as v3/ });
    for (const name of [/Edit as v3/, /Ask Tola to draft v3/]) {
      const button = screen.getByRole('button', { name }) as HTMLButtonElement;
      expect(button.disabled).toBe(true);
      fireEvent.click(button);
    }
    expect(screen.getAllByText('Not available yet').length).toBeGreaterThanOrEqual(2);
    expect(calls.filter((c) => c.method === 'POST')).toEqual([]);
  });
});

describe('access, versions and failures', () => {
  it.each([403, 404])('%s shows one not-open state with no title', async (status) => {
    docAnswers = [() => json(status, { code: 'x', message: 'Hidden.' })];
    await open();
    await screen.findByRole('heading', { level: 1, name: 'You can’t open this document' });
    expect(screen.queryByText(/Statement of work/)).toBeNull();
    expect(screen.queryByText(/Scope/)).toBeNull();
  });

  it('401 shows the sign-in link back to this page', async () => {
    docAnswers = [() => json(401, { code: 'not_signed_in', message: 'Sign in.' })];
    await open();
    const link = await screen.findByRole('link', { name: 'Sign in' });
    expect(link.getAttribute('href')).toBe('/accounts/login/?next=%2Fprojects%2FP-0101%2Fdocuments%2FD-2901%3Fv%3D2');
  });

  it.each([[''], ['latest'], ['0'], ['2x']])('a missing or unreadable version (%j) is not found and requests nothing', async (v) => {
    nav.search = v ? `v=${v}` : '';
    await open();
    await screen.findByRole('heading', { level: 1, name: 'You can’t open this document' });
    expect(gets('/api/v1/documents/')).toHaveLength(0);
  });

  it('a document that names another project is never shown under this address', async () => {
    docAnswers = [() => json(200, { ...docV2(), case_id: 'P-0999' })];
    await open();
    await screen.findByRole('heading', { level: 1, name: 'You can’t open this document' });
    expect(screen.queryByText(/Scope/)).toBeNull();
  });

  it('a read failure shows Try again that reads again', async () => {
    docAnswers = [() => json(500, { code: 'server_error', message: 'Oops.' }), () => json(200, docV2())];
    await open();
    fireEvent.click(await screen.findByRole('button', { name: 'Try again' }));
    await heading();
    expect(gets('/api/v1/documents/')).toHaveLength(2);
  });

  it('the requested version is the one read', async () => {
    nav.search = 'v=1';
    docAnswers = [() => json(200, { ...docV2(), version: '1', review: { role_label: 'PMO Lead' } })];
    await open();
    expect((await heading()).textContent).toBe('Statement of work · v1');
    expect(gets('/api/v1/documents/')[0].path).toBe('/api/v1/documents/D-2901/versions/1');
  });
});
