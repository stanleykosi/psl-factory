// @vitest-environment jsdom
// F-72: the document review page (SCR-08) on the live document-review contract, against a fetch stub that stands in for
// the contract mock (whose bodies are checked against the live contract in mock-live-document-review.test.ts).
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DocumentReviewPage } from '@/features/documents/DocumentReview';
import { AppShell } from '@/shell/AppShell';
import { bellFeed, isBellFeed, isRoleDashboard, roleDashboard } from './bell-feed';
import { matchingSources } from './source-files';

configure({ asyncUtilTimeout: 4000 });

vi.mock('next/navigation', () => ({
  usePathname: () => '/projects/P-0101/documents/2901',
  useSearchParams: () => new URLSearchParams(''),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = <T,>(name: string): T => JSON.parse(readFileSync(join(fixtures, name), 'utf8')) as T;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
type Doc = { title: string; version: number; revision: number; audience: string; current: boolean; decisions: string[]; django_url: string; preview: { field: string; text: string }[] };
type Pub = { review_status: string | null; findings: string[] } & Record<string, unknown>;
const doc = (patch: Partial<Doc> = {}): Doc => ({ ...read<Doc>('documents/review-2901.json'), ...patch });
const pub = (patch: Partial<Pub> = {}): Pub => ({ ...read<Pub>('documents/review-2901.publication.json'), ...patch });

type Call = { method: string; path: string; body: Record<string, unknown> | undefined; csrf: string | null };
let calls: Call[];
let docAnswers: (() => Response)[];
let pubAnswers: (() => Response)[];
let write: () => Response;

const REVIEW = '/api/v1/projects/P-0101/document-reviews/2901';
const reads = () => calls.filter((c) => c.method === 'GET' && c.path === REVIEW);
const pubReads = () => calls.filter((c) => c.method === 'GET' && c.path === `${REVIEW}/publication`);
const posts = () => calls.filter((c) => c.method === 'POST');
const next = (list: (() => Response)[]) => (list.length > 1 ? list.shift()! : list[0])();

beforeEach(() => {
  calls = [];
  docAnswers = [() => json(200, doc())];
  pubAnswers = [() => json(200, pub())];
  write = () => json(200, { review_id: 55, verdict: 'approve' });
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
      if (isRoleDashboard(request)) return roleDashboard();
      const url = new URL(request.url);
      const text = request.method === 'GET' ? '' : await request.clone().text();
      calls.push({ method: request.method, path: url.pathname, body: text ? JSON.parse(text) : undefined, csrf: request.headers.get('X-CSRFToken') });
      if (url.pathname === '/api/v1/me') return json(200, read('me.pm.json'));
      if (url.pathname === '/api/v1/projects/P-0101') return json(200, read('projects/P-0101.json'));
      if (url.pathname === REVIEW) return request.method === 'POST' ? write() : next(docAnswers);
      if (url.pathname === `${REVIEW}/publication`) return next(pubAnswers);
      return json(404, { code: 'not_found', message: 'Not here.' });
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function phone() {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: query.includes('max-width'), media: query, addEventListener: () => {}, removeEventListener: () => {} }));
}
function open(documentId = '2901') {
  render(
    <AppShell>
      <DocumentReviewPage caseId="P-0101" documentId={documentId} />
    </AppShell>,
  );
}
const heading = () => screen.findByRole('heading', { level: 1, name: /Statement of work/ });
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const NOTE = 'Note for the PM';
const type = (text: string) => fireEvent.change(screen.getByLabelText(NOTE), { target: { value: text } });
const press = async (name: string) => {
  await act(async () => {
    fireEvent.click(button(name));
  });
};
const decisionButtons = () => screen.queryAllByRole('button').map((b) => b.textContent).filter((t) => /Approve|Return/.test(t ?? ''));
const NO_ACCESS = 'You can’t open this document';

describe('reading the document', () => {
  it('reads the preview by its integer id and shows title, version, status, audience and numbered sections as plain text', async () => {
    docAnswers = [() => json(200, doc({ preview: [{ field: 'Scope <b>bold</b>', text: 'First <script>x()</script> paragraph.\n\nSecond paragraph.' }, { field: 'Fees', text: 'Fixed.' }] }))];
    open();
    expect((await heading()).textContent).toBe('Statement of work · v2');
    expect(reads()).toHaveLength(1);
    expect(pubReads()).toHaveLength(1);
    expect(await screen.findByText('Awaiting PMO Lead review')).toBeTruthy();
    expect(screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['1. Scope <b>bold</b>', '2. Fees']);
    expect(screen.getByText('First <script>x()</script> paragraph.')).toBeTruthy();
    expect(screen.getByText('Second paragraph.')).toBeTruthy();
    expect(screen.getByText('Client · Lagoon Health')).toBeTruthy();
    expect(screen.queryByText('/legacy/unused')).toBeNull();
  });

  it('the crumb is the project title and Documents, with no reference', async () => {
    open();
    await heading();
    const crumb = await screen.findByRole('navigation', { name: 'Breadcrumb' });
    await waitFor(() => expect(crumb.textContent).toBe('Lagoon Health · patient app / Documents'));
    expect(within(crumb).getByRole('link').getAttribute('href')).toBe('/projects/P-0101');
  });

  it('a project read that fails leaves the crumb as Documents and the page working', async () => {
    const stub = globalThis.fetch;
    vi.stubGlobal('fetch', async (request: Request) => (new URL(request.url).pathname === '/api/v1/projects/P-0101' ? json(500, { code: 'server_error', message: 'x' }) : stub(request)));
    open();
    await heading();
    expect(screen.getAllByRole('heading', { level: 3 })).not.toHaveLength(0);
    const crumb = await screen.findByRole('navigation', { name: 'Breadcrumb' });
    expect(crumb.textContent).toBe('Documents');
  });

  it('shows the status text as sent and a neutral tag when the version is not the current one', async () => {
    docAnswers = [() => json(200, doc({ current: false, decisions: [] }))];
    pubAnswers = [() => json(200, pub({ review_status: 'Returned to PM, then "revised"' }))];
    open();
    await heading();
    expect(await screen.findByText('Returned to PM, then "revised"')).toBeTruthy();
    expect(screen.getByText('Not the current version')).toBeTruthy();
  });

  it('an empty preview says so', async () => {
    docAnswers = [() => json(200, doc({ preview: [] }))];
    open();
    expect(await screen.findByText('This document has no sections yet.')).toBeTruthy();
  });

  it('a failed publication read leaves the document, sections and controls, with no status tag', async () => {
    pubAnswers = [() => json(500, { code: 'server_error', message: 'x' })];
    open();
    await heading();
    expect(await screen.findByRole('button', { name: 'Approve v2' })).toBeTruthy();
    expect(screen.queryByText('Awaiting PMO Lead review')).toBeNull();
    expect(screen.queryByText(/Not ready to decide yet/)).toBeNull();
    expect(screen.queryByText(/We couldn’t load/)).toBeNull();
  });

  it('a 200 that is not a document is the error state, not a half page', async () => {
    docAnswers = [() => json(200, { title: 'x' })];
    open();
    expect(await screen.findByText(/We couldn’t load this document/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Approve/ })).toBeNull();
  });

  it('a server error shows Retry, which reads again', async () => {
    docAnswers = [() => json(500, { code: 'server_error', message: 'x' }), () => json(200, doc())];
    open();
    fireEvent.click(await screen.findByRole('button', { name: /Try again|Retry/ }));
    await heading();
    expect(reads()).toHaveLength(2);
  });

  it('lists the findings as plain sentences under "Not ready to decide yet"', async () => {
    docAnswers = [() => json(200, doc({ decisions: [] }))];
    pubAnswers = [() => json(200, pub({ review_status: null, findings: ['Section Fees is empty.', 'Cost <i>missing</i>.'] }))];
    open();
    expect(await screen.findByText('Not ready to decide yet')).toBeTruthy();
    expect(screen.getByText('Section Fees is empty.')).toBeTruthy();
    expect(screen.getByText('Cost <i>missing</i>.')).toBeTruthy();
  });
});

describe('the id in the address', () => {
  it.each(['abc', '0', '2.5', '02', '-1', '12345678901234567890', '9223372036854775808', '2901/x', ' 2901', '2901?v=2'])('%s sends no document request', async (id) => {
    open(id);
    expect(await screen.findByText(NO_ACCESS)).toBeTruthy();
    await new Promise((r) => setTimeout(r, 20));
    expect(calls.filter((c) => c.path.includes('document-reviews'))).toEqual([]);
  });

  it('the largest id is sent with every digit', async () => {
    open('9223372036854775807');
    await waitFor(() => expect(calls.some((c) => c.path === '/api/v1/projects/P-0101/document-reviews/9223372036854775807')).toBe(true));
  });

  it('403 and 404 show the same words and nothing about the document', async () => {
    const shown: string[] = [];
    for (const status of [403, 404]) {
      docAnswers = [() => json(status, { code: status === 403 ? 'forbidden' : 'not_found', message: 'Statement of work is secret.' })];
      open();
      await screen.findByText(NO_ACCESS);
      shown.push(document.body.textContent ?? '');
      expect(screen.queryByText(/Statement of work/)).toBeNull();
      expect(screen.queryByText(/secret/)).toBeNull();
      cleanup();
      calls = [];
    }
    expect(shown[0]).toBe(shown[1]);
  });
});

describe('the controls follow the decisions the response offers', () => {
  it('approve and return: both buttons', async () => {
    open();
    await screen.findByRole('button', { name: 'Approve v2' });
    expect(decisionButtons()).toEqual(['Approve v2', 'Return with note']);
    expect(screen.getByLabelText(NOTE)).toBeTruthy();
  });

  it('return only: only Return', async () => {
    docAnswers = [() => json(200, doc({ decisions: ['return'] }))];
    open();
    await screen.findByRole('button', { name: 'Return with note' });
    expect(decisionButtons()).toEqual(['Return with note']);
  });

  it('none: no controls and one line saying so', async () => {
    docAnswers = [() => json(200, doc({ decisions: [] }))];
    open();
    await heading();
    expect(await screen.findByText('No decision is open to you on this version.')).toBeTruthy();
    expect(decisionButtons()).toEqual([]);
    expect(screen.queryByLabelText(NOTE)).toBeNull();
  });

  it('reject is not drawn', async () => {
    docAnswers = [() => json(200, doc({ decisions: ['approve', 'return', 'reject'] }))];
    open();
    await screen.findByRole('button', { name: 'Approve v2' });
    expect(screen.queryByRole('button', { name: /reject/i })).toBeNull();
    expect(decisionButtons()).toEqual(['Approve v2', 'Return with note']);
  });

  it('the dropped parts are gone', async () => {
    open();
    await screen.findByRole('button', { name: 'Approve v2' });
    for (const gone of [/TEST TEMPLATE/i, /changed since/i, /Compare/, /Checks/, /Held|Blocked/, /Returned by/, /flagged/]) expect(screen.queryByText(gone)).toBeNull();
    expect(screen.queryByRole('button', { name: /Compare|Edit as/ })).toBeNull();
    expect(matchingSources([join(__dirname, '../src/features/documents')], /django_url/)).toEqual([]);
  });
});

describe('recording a decision', () => {
  it('approve sends exactly the four keys with the read revision, then re-reads and shows the live result', async () => {
    open();
    await screen.findByRole('button', { name: 'Approve v2' });
    docAnswers = [() => json(200, doc({ revision: 8, decisions: [] }))];
    pubAnswers = [() => json(200, pub({ review_status: 'Approved' }))];
    type('Figures match the costing.');
    await press('Approve v2');
    await screen.findByText('You approved v2');
    expect(posts()).toHaveLength(1);
    expect(posts()[0]).toMatchObject({ path: REVIEW, body: { expected_revision: 7, verdict: 'approve', delegated: false, note: 'Figures match the costing.' }, csrf: 'mock-csrf-pm' });
    expect(Object.keys(posts()[0].body!).sort()).toEqual(['delegated', 'expected_revision', 'note', 'verdict']);
    expect(screen.getByRole('status').textContent).toBe('You approved v2. Not sent to the client.');
    expect(await screen.findByText('Approved')).toBeTruthy();
    expect(decisionButtons()).toEqual([]);
    expect(screen.getByText('No decision is open to you on this version.')).toBeTruthy();
    expect(calls.filter((c) => /\/(tasks|work)\b/.test(c.path))).toEqual([]);
    expect(reads()).toHaveLength(2);
    expect(pubReads()).toHaveLength(2);
  });

  it('return sends the verdict and says "You returned v2."', async () => {
    open();
    await screen.findByRole('button', { name: 'Return with note' });
    docAnswers = [() => json(200, doc({ revision: 8, decisions: [] }))];
    write = () => json(200, { review_id: 56, verdict: 'return' });
    type('Section 4 needs the week.');
    await press('Return with note');
    await waitFor(() => expect(screen.getByRole('status').textContent).toBe('You returned v2.'));
    expect(posts()[0].body).toEqual({ expected_revision: 7, verdict: 'return', delegated: false, note: 'Section 4 needs the week.' });
  });

  it('says nothing is recorded until the re-read confirms it, and Try again only re-reads', async () => {
    open();
    await screen.findByRole('button', { name: 'Approve v2' });
    docAnswers = [() => json(500, { code: 'server_error', message: 'x' })];
    type('ok');
    await press('Approve v2');
    await screen.findByText(/We couldn’t reload to confirm it was recorded/);
    expect(screen.queryByText(/You approved/)).toBeNull();
    expect(button('Approve v2').disabled).toBe(true);
    docAnswers = [() => json(200, doc({ revision: 8, decisions: [] }))];
    await press('Try again');
    await screen.findByText('You approved v2');
    expect(posts()).toHaveLength(1);
  });

  it('an empty or blank note sends nothing, says why and focuses the note, for both verdicts', async () => {
    open();
    await screen.findByRole('button', { name: 'Approve v2' });
    for (const [name, text] of [['Approve v2', ''], ['Return with note', '   ']]) {
      type(text);
      await press(name);
      expect(await screen.findByText('Add a note to record your decision.')).toBeTruthy();
      expect(document.activeElement).toBe(screen.getByLabelText(NOTE));
    }
    expect(posts()).toHaveLength(0);
  });

  it('a 4001-character note sends nothing; 4000 is sent', async () => {
    open();
    await screen.findByRole('button', { name: 'Approve v2' });
    type('x'.repeat(4001));
    await press('Approve v2');
    expect(await screen.findByText('Keep the note to 4000 characters or fewer.')).toBeTruthy();
    expect(posts()).toHaveLength(0);
    type('x'.repeat(4000));
    await press('Approve v2');
    await waitFor(() => expect(posts()).toHaveLength(1));
  });

  it('a double press sends one write', async () => {
    let release: () => void = () => {};
    write = () => json(200, { review_id: 55, verdict: 'approve' });
    open();
    await screen.findByRole('button', { name: 'Approve v2' });
    type('ok');
    const gate = new Promise<void>((resolve) => (release = resolve));
    const original = globalThis.fetch;
    vi.stubGlobal('fetch', async (request: Request) => {
      if (request.method === 'POST') await gate;
      return original(request);
    });
    await act(async () => {
      fireEvent.click(button('Approve v2'));
      fireEvent.click(button('Approve v2'));
      fireEvent.click(button('Return with note'));
    });
    release();
    await waitFor(() => expect(screen.getByText('You approved v2')).toBeTruthy());
    expect(posts()).toHaveLength(1);
  });

  it('a 409 records nothing, loads the latest, keeps the note, and the next press sends the new revision', async () => {
    open();
    await screen.findByRole('button', { name: 'Approve v2' });
    write = () => json(409, { code: 'stale_revision', message: 'x' });
    docAnswers = [() => json(200, doc({ revision: 9 }))];
    type('My note');
    await press('Approve v2');
    await screen.findByText(/This document changed while you were reading it, so nothing was recorded/);
    expect((screen.getByLabelText(NOTE) as HTMLTextAreaElement).value).toBe('My note');
    expect(reads()).toHaveLength(2);
    expect(screen.queryByText(/You approved/)).toBeNull();
    write = () => json(200, { review_id: 55, verdict: 'approve' });
    await press('Approve v2');
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts()[1].body).toMatchObject({ expected_revision: 9, note: 'My note' });
  });

  it('a 422 action_unavailable shows its message and the controls follow the new decisions', async () => {
    open();
    await screen.findByRole('button', { name: 'Approve v2' });
    write = () => json(422, { code: 'action_unavailable', message: 'A section is empty, so this cannot be decided yet.' });
    docAnswers = [() => json(200, doc({ revision: 8, decisions: [] }))];
    pubAnswers = [() => json(200, pub({ review_status: null, findings: ['Section Fees is empty.'] }))];
    type('ok');
    await press('Approve v2');
    await screen.findByText('A section is empty, so this cannot be decided yet.');
    await screen.findByText('Not ready to decide yet');
    expect(screen.getByText('Section Fees is empty.')).toBeTruthy();
    expect(decisionButtons()).toEqual([]);
  });

  it('a 422 on the note field shows on the note and the note stays', async () => {
    open();
    await screen.findByRole('button', { name: 'Approve v2' });
    write = () => json(422, { code: 'invalid', message: 'Check the note.', fields: [{ name: 'note', message: 'That note can’t be used.' }] });
    type('bad');
    await press('Return with note');
    expect(await screen.findByText('That note can’t be used.')).toBeTruthy();
    expect((screen.getByLabelText(NOTE) as HTMLTextAreaElement).value).toBe('bad');
    expect(reads()).toHaveLength(1);
  });

  it('a 403 on the write says so and re-reads', async () => {
    open();
    await screen.findByRole('button', { name: 'Approve v2' });
    write = () => json(403, { code: 'forbidden', message: 'Your role does not allow this.' });
    docAnswers = [() => json(200, doc({ revision: 8, decisions: [] }))];
    type('ok');
    await press('Approve v2');
    await screen.findByText('You can’t record a decision on this document.');
    await waitFor(() => expect(decisionButtons()).toEqual([]));
    expect(reads()).toHaveLength(2);
  });

  it('an expired token records nothing and asks for another press', async () => {
    open();
    await screen.findByRole('button', { name: 'Approve v2' });
    write = () => json(403, { code: 'csrf_failed', message: 'x' });
    type('ok');
    await press('Approve v2');
    await screen.findByText(/Your session was refreshed\. Press the action again\. Nothing was changed\./);
    expect(posts()).toHaveLength(1);
    expect(button('Approve v2').disabled).toBe(false);
  });

  it('a 5xx on the write is uncertain: buttons off, one POST, and Try again only reads', async () => {
    open();
    await screen.findByRole('button', { name: 'Approve v2' });
    write = () => json(500, { code: 'server_error', message: 'x' });
    type('ok');
    await press('Approve v2');
    await screen.findByText('We couldn’t confirm whether your decision was recorded.');
    expect(button('Approve v2').disabled).toBe(true);
    expect(button('Return with note').disabled).toBe(true);
    expect(screen.queryByText(/You approved/)).toBeNull();
    const before = reads().length;
    await press('Try again');
    await waitFor(() => expect(reads().length).toBe(before + 1));
    expect(posts()).toHaveLength(1);
    expect(screen.queryByText('We couldn’t confirm whether your decision was recorded.')).toBeNull();
    expect(button('Approve v2').disabled).toBe(false);
  });

  it('a network failure on the write is uncertain too', async () => {
    open();
    await screen.findByRole('button', { name: 'Approve v2' });
    const original = globalThis.fetch;
    vi.stubGlobal('fetch', async (request: Request) => {
      if (request.method === 'POST') throw new TypeError('offline');
      return original(request);
    });
    type('ok');
    await press('Approve v2');
    await screen.findByText('We couldn’t confirm whether your decision was recorded.');
    expect(button('Approve v2').disabled).toBe(true);
  });
});

describe('on a phone', () => {
  it('Approve opens the same note sheet as Return; the note is checked, then sent', async () => {
    phone();
    open();
    await screen.findByRole('button', { name: 'Approve' });
    expect(screen.queryByLabelText(NOTE)).toBeNull();
    await act(async () => {
      fireEvent.click(button('Approve'));
    });
    const dialog = await screen.findByRole('dialog', { name: 'Approve with a note' });
    await press('Approve v2');
    expect(within(dialog).getByText('Add a note to record your decision.')).toBeTruthy();
    expect(posts()).toHaveLength(0);
    docAnswers = [() => json(200, doc({ revision: 8, decisions: [] }))];
    type('Looks right.');
    await press('Approve v2');
    await screen.findByText('You approved v2');
    expect(posts()[0].body).toEqual({ expected_revision: 7, verdict: 'approve', delegated: false, note: 'Looks right.' });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('Return opens its own sheet', async () => {
    phone();
    open();
    await screen.findByRole('button', { name: 'Return' });
    await act(async () => {
      fireEvent.click(button('Return'));
    });
    expect(await screen.findByRole('dialog', { name: 'Return with a note' })).toBeTruthy();
    expect(button('Return with note')).toBeTruthy();
  });
});
