// @vitest-environment jsdom
// F-34 SCR-46: the hypercare work item as the fixtures return it (contract mock only). Nothing here deploys, evaluates or
// qualifies anything: every day count, window, criterion and "qualified" is fixture text. Four states, the hold with no
// controls, "qualified" only when the response says verified, Unknown, controls only from the response, the writes, the
// done notice waiting for the re-read, access.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { StrictMode } from 'react';

import { act, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { WorkItem } from '@/features/work-item/labels';
import { WorkItemView } from '@/features/work-item/WorkItemView';
import { AppShell } from '@/shell/AppShell';
import { setWhen } from './controls';
import { withoutBellFeed } from './bell-feed';

configure({ asyncUtilTimeout: 5000 });

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-3101',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock('@/features/response/reload', () => ({ reloadPage: vi.fn() }));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const item = (name: string): WorkItem => read(`work/${name}.json`);
const persona = (name: string) => read(`me.${name}.json`);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

type Sent = { method: string; path: string; body: Record<string, unknown> | undefined; csrf: string | null };
type Answer = Response | Promise<Response> | (() => Response | Promise<Response>);
let sent: Sent[];
let itemAnswers: (WorkItem | (() => Response | Promise<Response>))[];
let stepAnswers: Answer[];
let uploadAnswers: Answer[];
let me: unknown;

const posts = (suffix = '/steps') => sent.filter((r) => r.method === 'POST' && r.path.endsWith(suffix));
const ok = (body: Record<string, unknown> = {}) => json(200, { work_id: 'W-0', state: 'ready', revision: 9, outcome: 'done', ...body });

beforeEach(() => {
  sent = [];
  itemAnswers = [];
  stepAnswers = [];
  uploadAnswers = [];
  me = persona('pm');
  const stub = vi.fn<(request: Request) => Promise<Response>>(async (request) => {
    const url = new URL(request.url);
    const text = request.method === 'GET' ? '' : await request.text();
    sent.push({ method: request.method, path: url.pathname, body: text ? JSON.parse(text) : undefined, csrf: request.headers.get('X-CSRFToken') });
    if (url.pathname === '/api/v1/me') return json(200, me);
    if (request.method === 'GET' && url.pathname.startsWith('/api/v1/work/')) {
      const next = itemAnswers.length > 1 ? itemAnswers.shift()! : itemAnswers[0];
      return typeof next === 'function' ? next() : json(200, next);
    }
    if (url.pathname.endsWith('/steps')) {
      const answer = stepAnswers.length > 1 ? stepAnswers.shift()! : (stepAnswers[0] ?? ok());
      return typeof answer === 'function' ? answer() : answer;
    }
    if (url.pathname.endsWith('/evidence')) {
      const answer = uploadAnswers.length > 1 ? uploadAnswers.shift()! : (uploadAnswers[0] ?? json(200, { evidence_id: 'EV-P-0101-1', sha256: 'a'.repeat(64), case_revision: 3 }));
      return typeof answer === 'function' ? answer() : answer;
    }
    return json(404, { code: 'not_found', message: 'Not here.' });
  });
  vi.stubGlobal('fetch', withoutBellFeed(stub));
});
afterEach(() => vi.unstubAllGlobals());

/** The item until a step has been sent, then `after` (a StrictMode page reads twice, so a read count can't tell). */
const afterStep = (first: WorkItem, after: WorkItem) => () => json(200, posts().length > 0 ? after : first);

/** Serves the item, then each later read in turn (the last one repeats). */
async function open(first: WorkItem, ...later: (WorkItem | (() => Response | Promise<Response>))[]) {
  itemAnswers = [first, ...later];
  const view = render(
    <StrictMode>
      <AppShell>
        <WorkItemView id={first.id} tab="overview" />
      </AppShell>
    </StrictMode>,
  );
  await screen.findByRole('heading', { level: 1, name: first.title });
  return view;
}

const ws = () => within(document.querySelector('.ws') as HTMLElement);
const pageText = () => document.body.textContent ?? '';
/** The notices at the top of the page; the agent's own "Done: …" lines are not in them. */
const notices = () => [document.querySelector('.ws-notices'), document.querySelector('.cmp-toasts')].map((el) => el?.textContent ?? '').join(' ');
const wsText = () => (document.querySelector('.ws') as HTMLElement).textContent ?? '';
const press = async (name: string) => {
  await act(async () => {
    fireEvent.click(ws().getByRole('button', { name }));
  });
};
// A date and a time is picked from the shared dropdown (D-158); anything else is typed.
const type = (label: string, value: string) =>
  /^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(value) ? setWhen(label, value, ws()) : fireEvent.change(ws().getByLabelText(new RegExp(label)), { target: { value } });
const rowOf = (text: string) => ws().getByText(text).closest('tr') as HTMLElement;

describe('four states from the fixture (AC 5)', () => {
  it('W-3101 running: status, observations, criteria, Next and the one step; nothing else', async () => {
    await open(item('W-3101'));
    expect(pageText()).toContain('Hypercare · day 10 of 30');
    expect(ws().getByRole('table').querySelectorAll('thead th')).toHaveLength(3);
    expect([...ws().getByRole('table').querySelectorAll('thead th')].map((th) => th.textContent)).toEqual(['Reference', 'What', 'State']);
    expect(ws().getByText('ISS-0301')).toBeTruthy();
    expect(ws().getByText('Login slow on older phones · medium')).toBeTruthy();
    expect(ws().getByText('Criteria · from Setup › Rules (PSL to confirm)')).toBeTruthy();
    expect(ws().getByText('30 days · from Setup')).toBeTruthy();
    expect(ws().getAllByText('Met')).toHaveLength(3);
    expect(ws().getByText(/Tola evaluates hypercare when the window ends on 01 May/)).toBeTruthy();
    expect(ws().getAllByRole('button').map((b) => b.textContent)).toEqual(['Log an observation']);
  });

  it('the criteria, window and day text come from the fixture only', async () => {
    const body = item('W-3101');
    body.workspace!.sections = body.workspace!.sections.filter((s) => s.key !== 'criteria');
    body.workspace!.status = { label: 'Hypercare · day 11 of 30', tone: 'person' };
    await open(body);
    expect(pageText()).toContain('Hypercare · day 11 of 30');
    expect(wsText()).not.toContain('Met');
    expect(wsText()).not.toContain('30 days');
    expect(wsText()).not.toContain('Criteria');
  });

  it('W-3102 record: the status, the Next line and the Record release button; the form is closed', async () => {
    await open(item('W-3102'));
    expect(pageText()).toContain('Hypercare · release not recorded');
    expect(ws().getByText(/Engineering deploys outside the factory/)).toBeTruthy();
    expect(ws().getAllByRole('button').map((b) => b.textContent)).toEqual(['Record release']);
    expect(ws().queryByRole('form')).toBeNull();
  });

  it('the criteria show only the returned Met tag, with no second result word (UI-1-1)', async () => {
    for (const id of ['W-3101', 'W-3104']) {
      const view = await open(item(id));
      const rows = [...document.querySelectorAll('.ws-rows--checklist > li')].filter((r) => r.textContent?.includes('Met'));
      expect(rows).toHaveLength(3);
      for (const row of rows) expect(row.textContent).not.toContain('Done');
      view.unmount();
    }
  });

  it('W-3104 qualified: the stage strip has no agent still working (UX-1-1)', async () => {
    const body = item('W-3104');
    expect(body.stations.map((st) => st.status)).not.toContain('current_agent');
    await open(body);
    expect(pageText()).not.toContain('Agent working');
  });

  it('W-3104 qualified: the status, the criteria and the closure link to W-3120', async () => {
    await open(item('W-3104'));
    expect(pageText()).toContain('Hypercare qualified');
    expect(ws().getByText(/Hypercare qualified on 01 May, verified/)).toBeTruthy();
    expect(ws().getAllByText('Met')).toHaveLength(3);
    expect(ws().getByRole('link', { name: 'See what closure needs' }).getAttribute('href')).toBe('/work/W-3120');
    expect(ws().queryAllByRole('button')).toHaveLength(0);
  });
});

describe('the hold, with no controls (AC 6)', () => {
  it('W-3103: the note, the observations, Next and the Setup link; no criteria, no MET and no button', async () => {
    await open(item('W-3103'));
    expect(pageText()).toContain('Setup needed');
    expect(ws().getByText(/Hypercare can't be evaluated/)).toBeTruthy();
    expect(ws().getByText('OBS-0012')).toBeTruthy();
    expect(ws().getByText(/An admin sets the criteria in Setup › Rules/)).toBeTruthy();
    expect(ws().getByRole('link', { name: 'Open Setup › Rules' }).getAttribute('href')).toBe('/setup/rules/delivery');
    expect(ws().queryByText('Met')).toBeNull();
    expect(wsText()).not.toContain('Criteria');
    expect(ws().queryAllByRole('button')).toHaveLength(0);
  });

  it('a copy with the link removed draws no Setup link; an unknown area or kind draws nothing', async () => {
    for (const links of [[], [{ key: 'k', label: 'Open Setup › Rules', target: { kind: 'setup_rules', area: 'nowhere' } }], [{ key: 'k', label: 'Open Setup › Rules', target: { kind: 'setup_rules' } }], [{ key: 'k', label: 'Open Setup › Rules', target: { kind: 'setup_rules', area: '__proto__' } }]]) {
      const body = item('W-3103');
      (body.workspace as unknown as { links: unknown }).links = links;
      const view = await open(body);
      expect(ws().queryByRole('link', { name: 'Open Setup › Rules' })).toBeNull();
      view.unmount();
    }
  });

  it('a known area other than delivery goes to that area’s rules', async () => {
    const body = item('W-3103');
    (body.workspace as unknown as { links: unknown }).links = [{ key: 'k', label: 'Open Finance rules', target: { kind: 'setup_rules', area: 'finance' } }];
    await open(body);
    expect(ws().getByRole('link', { name: 'Open Finance rules' }).getAttribute('href')).toBe('/setup/rules/finance');
  });
});

describe('qualified only when the response says verified (AC 7, INV-AGENT)', () => {
  it('W-3110: Tola marked it done, but no green banner, no "qualified" and no closure link', async () => {
    await open(item('W-3110'));
    expect(pageText()).toContain('Hypercare · day 30 of 30');
    expect(wsText().toLowerCase()).not.toContain('qualified by');
    expect(pageText()).not.toContain('Hypercare qualified');
    expect(ws().queryByRole('link', { name: 'See what closure needs' })).toBeNull();
    expect(document.querySelector('.ws .psl-callout--success')).toBeNull();
  });

  it('W-3104 is the green banner; the same item with status tone person is the amber one', async () => {
    const view = await open(item('W-3104'));
    expect(document.querySelector('.ws .psl-callout--success')).toBeTruthy();
    view.unmount();
    const body = item('W-3104');
    body.workspace!.status = { label: 'Hypercare qualified', tone: 'person' };
    await open(body);
    expect(document.querySelector('.ws .psl-callout--success')).toBeNull();
    expect(document.querySelector('.ws .psl-callout--warning')).toBeTruthy();
  });
});

describe('Unknown, not zero (AC 8)', () => {
  it('W-3111: the Incidents state, the Window and the unknown criterion each read Unknown', async () => {
    await open(item('W-3111'));
    const incidents = rowOf('Incidents');
    expect(within(incidents).getByText('Unknown')).toBeTruthy();
    expect(incidents.textContent).not.toMatch(/None|\b0\b/);
    const rows = [...document.querySelectorAll('.ws-rows--checklist > li')];
    const window = rows.find((r) => r.textContent?.startsWith('Window'))!;
    const unknownCriterion = rows.find((r) => r.textContent?.startsWith('No unresolved incidents'))!;
    expect(window.textContent).toContain('Unknown');
    expect(unknownCriterion.textContent).toContain('Unknown');
    expect(unknownCriterion.textContent).not.toContain('Met');
  });

  it('a tag cell with no tag and no text, or a missing cell, reads Unknown (shared fix 1)', async () => {
    const body = item('W-3101');
    const table = body.workspace!.sections[0];
    table.items[0].cells = table.items[0].cells!.filter((c) => c.column !== 'state');
    table.items[1].cells = table.items[1].cells!.map((c) => (c.column === 'state' ? { column: 'state' } : c));
    await open(body);
    expect(within(rowOf('ISS-0301')).getByText('Unknown')).toBeTruthy();
    expect(within(rowOf('OBS-0012')).getByText('Unknown')).toBeTruthy();
  });
});

describe('controls only from the response (AC 9)', () => {
  it('W-3109: Log an observation is unavailable, described by its reason, and sends nothing', async () => {
    await open(item('W-3109'));
    const control = ws().getByRole('button', { name: 'Log an observation' });
    expect(control.getAttribute('aria-disabled')).toBe('true');
    expect(document.getElementById(control.getAttribute('aria-describedby')!)?.textContent).toBe("Only the project's PM logs observations.");
    await press('Log an observation');
    expect(ws().queryByRole('form')).toBeNull();
    expect(posts()).toHaveLength(0);
  });

  it('every persona sees the same controls for the same fixture', async () => {
    const seen: string[][] = [];
    for (const who of ['pm', 'finance_lead', 'ceo']) {
      me = persona(who);
      const view = await open(item('W-3101'));
      seen.push(ws().getAllByRole('button').map((b) => b.textContent ?? ''));
      view.unmount();
    }
    expect(seen).toEqual([['Log an observation'], ['Log an observation'], ['Log an observation']]);
  });

  it('a copy of W-3101 without the step draws no button', async () => {
    const body = item('W-3101');
    delete body.workspace!.steps;
    await open(body);
    expect(ws().queryAllByRole('button')).toHaveLength(0);
  });
});

describe('record the release (AC 10, 12, 14)', () => {
  const file = () => new File(['%PDF-1.4'], 'release-1.0.0-log.pdf', { type: 'application/pdf' });
  const upload = async () => {
    const input = document.querySelector('.ws input[type="file"]') as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { files: [file()] } });
    });
    await waitFor(() => expect(posts('/evidence')).toHaveLength(1));
    await waitFor(() => expect(screen.queryByText(/Uploading…/)).toBeNull());
    // the proof only counts once the page has taken the upload's answer: wait until it stops asking for proof
    await waitFor(() => expect(screen.queryByText('Add proof to continue.')).toBeNull());
  };

  it('opens with Version and Environment filled and the consequence; blank fields and no proof send nothing', async () => {
    await open(item('W-3102'));
    await press('Record release');
    const form = ws().getByRole('form');
    expect((within(form).getByLabelText(/Version/) as HTMLInputElement).value).toBe('Build 1.0.0');
    expect((within(form).getByLabelText(/Environment/) as HTMLInputElement).value).toBe('Production · Lagoon Health');
    expect(wsText()).toContain('the hypercare window starts from the release date');
    await act(async () => {
      fireEvent.submit(form);
    });
    expect(posts()).toHaveLength(0);
    expect(posts('/evidence')).toHaveLength(0);
    expect(form.textContent).toMatch(/Released on/);
  });

  it('the "add proof" message goes once a file is uploaded (UX-1-2)', async () => {
    await open(item('W-3102'));
    await press('Record release');
    await act(async () => {
      fireEvent.submit(ws().getByRole('form'));
    });
    expect(wsText()).toContain('Add proof to continue');
    await upload();
    await waitFor(() => expect(wsText()).not.toContain('Add proof to continue'));
  });

  it('uploads the proof with kind deployment_log and the case revision, then sends record_release once and shows the re-read hold', async () => {
    stepAnswers = [ok()];
    await open(item('W-3102'), afterStep(item('W-3102'), item('W-3102.next')));
    await press('Record release');
    type('Released on', '2026-04-01T22:00');
    await upload();
    expect(posts('/evidence')[0].body).toMatchObject({ kind: 'deployment_log', case_revision: 2 });
    expect(posts('/evidence')[0].csrf).toBeTruthy();
    await act(async () => {
      fireEvent.submit(ws().getByRole('form'));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    const [step] = posts();
    expect(step.body).toMatchObject({ step: 'record_release', expected_revision: 1, evidence_ids: ['EV-P-0101-1'], inputs: { version: 'Build 1.0.0', environment: 'Production · Lagoon Health' } });
    expect(typeof (step.body!.inputs as Record<string, unknown>).released_at).toBe('string');
    expect(step.body!.idempotency_key).toBeTruthy();
    expect(step.csrf).toBeTruthy();
    await waitFor(() => expect(pageText()).toContain('Setup needed'));
    expect(ws().queryAllByRole('button')).toHaveLength(0);
  });

  it('a failed upload shows the proof problem and sends no step', async () => {
    uploadAnswers = [json(500, { code: 'server_error', message: 'No.' })];
    await open(item('W-3102'));
    await press('Record release');
    type('Released on', '2026-04-01T22:00');
    const input = document.querySelector('.ws input[type="file"]') as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { files: [file()] } });
    });
    await waitFor(() => expect(posts('/evidence')).toHaveLength(1));
    await act(async () => {
      fireEvent.submit(ws().getByRole('form'));
    });
    expect(posts()).toHaveLength(0);
  });

  it('a 422 naming released_at keeps the form; a 403 says so and re-reads', async () => {
    stepAnswers = [json(422, { code: 'invalid', message: 'Check these fields: released_at.', fields: [{ name: 'released_at', message: 'Use a date after go-live.' }] })];
    await open(item('W-3102'));
    await press('Record release');
    type('Released on', '2026-04-01T22:00');
    await upload();
    await act(async () => {
      fireEvent.submit(ws().getByRole('form'));
    });
    await waitFor(() => expect(pageText()).toContain('Use a date after go-live.'));
    expect(ws().getByRole('form')).toBeTruthy();

    stepAnswers = [json(403, { code: 'forbidden', message: 'No.' })];
    await act(async () => {
      fireEvent.submit(ws().getByRole('form'));
    });
    await waitFor(() => expect(pageText()).toContain('You can’t take that step.'));
  }, 30000);

  it('a 500 shows the failed message, never "Done" or "recorded", and re-reads', async () => {
    stepAnswers = [json(500, { code: 'server_error', message: 'x' })];
    await open(item('W-3105'));
    await press('Record release');
    type('Released on', '2026-04-01T22:00');
    await upload();
    const reads = () => sent.filter((r) => r.method === 'GET' && r.path === '/api/v1/work/W-3105').length;
    const before = reads();
    await act(async () => {
      fireEvent.submit(ws().getByRole('form'));
    });
    await waitFor(() => expect(pageText()).toContain('We couldn’t confirm this step. Check the page before trying again.'));
    expect(notices()).not.toMatch(/Done:|recorded/i);
    await waitFor(() => expect(reads()).toBeGreaterThan(before));
    expect(pageText()).toContain('Hypercare · release not recorded');
  });

  it('effect_uncertain locks every step and says it is being checked', async () => {
    stepAnswers = [ok({ outcome: 'effect_uncertain', message: 'The release may not have been recorded.' })];
    await open(item('W-3107'));
    await press('Record release');
    type('Released on', '2026-04-01T22:00');
    await upload();
    await act(async () => {
      fireEvent.submit(ws().getByRole('form'));
    });
    await waitFor(() => expect(pageText()).toContain('We are checking what happened. Nothing was sent again.'));
    expect(notices()).not.toContain('Done:');
    expect(ws().getByRole('button', { name: 'Record release' }).getAttribute('aria-disabled')).toBe('true');
  });

  it('a 409 shows the new version and keeps the form', async () => {
    stepAnswers = [json(409, { code: 'conflict', message: 'Changed.' })];
    const next = item('W-3108.next');
    await open(item('W-3108'), afterStep(item('W-3108'), next));
    await press('Record release');
    type('Released on', '2026-04-01T22:00');
    await upload();
    await act(async () => {
      fireEvent.submit(ws().getByRole('form'));
    });
    await waitFor(() => expect(pageText()).toContain('This changed while you were working. Showing version 2.'));
    expect(ws().getByRole('form')).toBeTruthy();
  });
});

describe('no success before the re-read (AC 11, shared fix 2)', () => {
  it('with the re-read pending after a 200, no Done text and no new row is on screen; once it resolves they appear together', async () => {
    let release!: (response: Response) => void;
    const pending = new Promise<Response>((resolve) => {
      release = resolve;
    });
    stepAnswers = [ok()];
    await open(item('W-3101'), () => (posts().length > 0 ? pending : json(200, item('W-3101'))));
    await press('Log an observation');
    type('What did you notice', 'Checkout page slow once on day 10');
    await act(async () => {
      fireEvent.submit(ws().getByRole('form'));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    // the step answered 200; the re-read has not
    await waitFor(() => expect(sent.filter((r) => r.method === 'GET' && r.path === '/api/v1/work/W-3101').length).toBeGreaterThan(1));
    expect(notices()).not.toContain('Done:');
    expect(ws().queryByText('OBS-0013')).toBeNull();
    await act(async () => {
      release(json(200, item('W-3101.next')));
    });
    await waitFor(() => expect(ws().getByText('OBS-0013')).toBeTruthy());
    // the toast renders after the re-read settles; wait for it rather than reading the same tick
    await waitFor(() => expect(notices()).toContain('Done: Log an observation.'));
  });
});

describe('log an observation (AC 13)', () => {
  it('a blank note sends nothing; with text one step goes with inputs.what and no evidence_ids; the re-read shows OBS-0013', async () => {
    await open(item('W-3101'), afterStep(item('W-3101'), item('W-3101.next')));
    await press('Log an observation');
    await act(async () => {
      fireEvent.submit(ws().getByRole('form'));
    });
    expect(posts()).toHaveLength(0);
    type('What did you notice', 'Checkout page slow once on day 10');
    await act(async () => {
      fireEvent.submit(ws().getByRole('form'));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).toMatchObject({ step: 'log_observation', expected_revision: 1, inputs: { what: 'Checkout page slow once on day 10' } });
    expect(posts()[0].body).not.toHaveProperty('evidence_ids');
    await waitFor(() => expect(rowOf('OBS-0013').textContent).toContain('Noted'));
  });

  it('with a proof, evidence_ids carries the uploaded id', async () => {
    await open(item('W-3101'), afterStep(item('W-3101'), item('W-3101.next')));
    await press('Log an observation');
    type('What did you notice', 'Checkout page slow once on day 10');
    const input = document.querySelector('.ws input[type="file"]') as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { files: [new File(['%PDF-1.4'], 'screenshot.pdf', { type: 'application/pdf' })] } });
    });
    await waitFor(() => expect(posts('/evidence')).toHaveLength(1));
    await waitFor(() => expect(screen.queryByText(/Uploading…/)).toBeNull());
    // the upload's answer has reached the form once its file chip shows
    await screen.findByText(/screenshot\.pdf/);
    expect(posts('/evidence')[0].body).toMatchObject({ kind: 'hypercare_observation' });
    await act(async () => {
      fireEvent.submit(ws().getByRole('form'));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].body).toMatchObject({ evidence_ids: ['EV-P-0101-1'] });
  });

  it('W-3112: written, then 500: the failed message and no Done; the re-read shows OBS-0013', async () => {
    stepAnswers = [json(500, { code: 'server_error', message: 'x' })];
    await open(item('W-3112'), afterStep(item('W-3112'), item('W-3112.next')));
    await press('Log an observation');
    type('What did you notice', 'Checkout page slow once on day 10');
    await act(async () => {
      fireEvent.submit(ws().getByRole('form'));
    });
    await waitFor(() => expect(pageText()).toContain('We couldn’t confirm this step. Check the page before trying again.'));
    expect(notices()).not.toContain('Done:');
    await waitFor(() => expect(ws().getByText('OBS-0013')).toBeTruthy());
  });
});

describe('access (AC 15)', () => {
  for (const [label, status, kind] of [['401', 401, 'unauthenticated'], ['403', 403, 'forbidden'], ['404', 404, 'not_found']] as const) {
    it(`a ${label} on the item shows no title, project, reference or row text`, async () => {
      itemAnswers = [() => json(status, { code: kind, message: 'x' })];
      render(
        <AppShell>
          <WorkItemView id="W-3101" tab="overview" />
        </AppShell>,
      );
      await waitFor(() => expect(document.querySelector('.ws')).toBeNull());
      await waitFor(() => expect(sent.some((r) => r.path === '/api/v1/work/W-3101')).toBe(true));
      const text = document.body.textContent ?? '';
      for (const secret of ['Lagoon Health', 'HYP-0062', 'ISS-0301', 'Hypercare']) expect(text).not.toContain(secret);
    });
  }

  it('a 404 on the step write shows the no-access view', async () => {
    stepAnswers = [json(404, { code: 'not_found', message: 'x' })];
    await open(item('W-3101'));
    await press('Log an observation');
    type('What did you notice', 'x');
    await act(async () => {
      fireEvent.submit(ws().getByRole('form'));
    });
    await waitFor(() => expect(document.querySelector('.ws')).toBeNull());
    expect(document.body.textContent).not.toContain('ISS-0301');
  });
});
