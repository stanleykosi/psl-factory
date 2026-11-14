// @vitest-environment jsdom
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { WorkItem } from '@/api/types';
import type { ResponseWorkItem } from '@/features/response';
import { reloadPage } from '@/features/response';
import { ResponseView } from '@/features/response/ResponseView';
import { WorkItemOverview } from '@/features/work-item/WorkItemOverview';
import { WorkItemView } from '@/features/work-item/WorkItemView';
import { AppShell } from '@/shell/AppShell';

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-1601/respond',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock('@/features/response/reload', () => ({ reloadPage: vi.fn() }));

const fixtures = join(__dirname, '../mock/fixtures');
const read = <T,>(name: string): T => JSON.parse(readFileSync(join(fixtures, name), 'utf8')) as T;
/** A served item: W-16xx from fixtures/response/work, sidecars ("W-1601.recorded") from fixtures/response, others from work/. */
const item = (name: string): ResponseWorkItem =>
  /^W-16\d\d$/.test(name) ? read(`response/work/${name}.json`) : name.startsWith('W-16') ? read(`response/${name}.json`) : read(`work/${name}.json`);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const STALE = { code: 'stale_revision', message: 'Someone changed this since you opened it. Reload to see the latest version.' };
const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow this.' };

type Call = { method: string; path: string; body: Record<string, unknown> | undefined; csrf: string | null };
type Answer = (n: number, call: Call) => Response | Promise<Response>;
let calls: Call[];
let answers: { me: string; item: Answer; upload: Answer; claim: Answer; respond: Answer; action: Answer };

const writes = () => calls.filter((c) => c.method === 'POST');
const posts = (suffix: string) => calls.filter((c) => c.method === 'POST' && c.path.endsWith(suffix));
const gets = () => calls.filter((c) => c.method === 'GET' && c.path.startsWith('/api/v1/work/')).length;

function recordedReply(body: Record<string, unknown>) {
  return {
    task_id: 'T-1601',
    work_state: 'ready',
    revision: 3,
    recorded: { by: { name: 'Tunde Bello', role: 'PM', is_you: true }, at: '2026-11-11T14:04:00Z', responded_at: body.responded_at, received_via: 'email', proof_count: 1 + ((body.evidence_ids as string[] | undefined)?.length ?? 0), summary: 'Client UAT sign-off for Lagoon Health' },
    next: ['The release line moves on to go-live readiness.', 'Milestone 2 can now be marked complete, which lets Chidi draft its invoice.'],
  };
}

beforeEach(() => {
  calls = [];
  vi.mocked(reloadPage).mockClear();
  answers = {
    me: 'pm',
    item: (_, c) => json(200, item(c.path.split('/')[4])),
    upload: (n, c) => json(200, { evidence_id: `EV-${c.path.split('/')[4]}-${n + 1}`, sha256: 'a'.repeat(64), case_revision: (c.body!.case_revision as number) + 1 }),
    claim: (_, c) => json(200, { task_id: c.path.split('/')[4], revision: (c.body!.expected_revision as number) + 1, claimed_by: 'Tunde Bello' }),
    respond: (_, c) => json(200, recordedReply(c.body!)),
    action: (_, c) => json(200, { work_id: c.path.split('/')[4], state: 'ready', revision: 7 }),
  };
  const n = { item: 0, upload: 0, claim: 0, respond: 0, action: 0 };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      const text = request.method === 'GET' ? '' : await request.clone().text();
      const c: Call = { method: request.method, path: url.pathname, body: text ? JSON.parse(text) : undefined, csrf: request.headers.get('X-CSRFToken') };
      calls.push(c);
      if (url.pathname === '/api/v1/me') return json(200, read(`me.${answers.me}.json`));
      if (url.pathname.endsWith('/evidence')) return answers.upload(n.upload++, c);
      if (url.pathname.endsWith('/claim')) return answers.claim(n.claim++, c);
      if (url.pathname.endsWith('/response')) return answers.respond(n.respond++, c);
      if (url.pathname.endsWith('/actions')) return answers.action(n.action++, c);
      return answers.item(n.item++, c);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
});

function phone() {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: query.includes('max-width'), media: query, addEventListener: () => {}, removeEventListener: () => {} }));
}

async function open(id = 'W-1601', taskId: string | undefined = 'T-1601') {
  render(
    <AppShell>
      <ResponseView id={id} taskId={taskId} />
    </AppShell>,
  );
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
}
/** The frame's phone bar holds the only way back (usePhoneBack); the page draws none of its own. */
async function expectPhoneBack(label: string, href: string) {
  const back = await screen.findByRole('link', { name: `Back to ${label}` });
  expect(back.textContent).toBe(`← ${label}`);
  expect(back.getAttribute('href')).toBe(href);
  expect(back.closest('.psl-phonebar')).toBeTruthy();
  expect(screen.getAllByText(/^← /)).toHaveLength(1);
  expect(screen.queryByRole('button', { name: 'Menu' })).toBeNull();
}
async function openWork(id: string) {
  render(
    <AppShell>
      <WorkItemView id={id} tab="overview" />
    </AppShell>,
  );
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
}

const text = () => document.body.textContent ?? '';
const crumb = () => document.querySelector('.resp-crumb') as HTMLElement;
const recordButton = (name: RegExp | string = /^Record (response|signature)$|^Recording…$/) => screen.getByRole('button', { name }) as HTMLButtonElement;
const fileInput = () => document.querySelector('input[type="file"]') as HTMLInputElement;
const pdf = (name = 'Lagoon_UAT_signoff_11Nov.pdf', size = 184 * 1024) => new File([new Uint8Array(size).fill(37)], name, { type: 'application/pdf' });

async function addFile(file = pdf()) {
  const before = posts('/evidence').length;
  fireEvent.change(fileInput(), { target: { files: [file] } });
  await waitFor(() => expect(posts('/evidence')).toHaveLength(before + 1));
  await waitFor(() => expect(screen.queryByText(/Uploading…/)).toBeNull());
}
function choose(label: string) {
  fireEvent.click(screen.getByRole('radio', { name: label }));
}
function when(value = '2026-11-11T16:20', label = 'When they responded') {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}
function tick() {
  fireEvent.click(screen.getByRole('checkbox'));
}
async function fillW1601({ file = true, attest = true } = {}) {
  choose('Approved');
  when();
  if (file) await addFile();
  if (attest) tick();
}

describe('entry from the work item (SCR-02 waiting)', () => {
  it('W-1601 links to the response form instead of the decision; W-1608 has neither; W-1201 keeps the decision', () => {
    const view = render(<WorkItemOverview id="W-1601" item={item('W-1601') as WorkItem} />);
    const panel = screen.getByRole('region', { name: 'Current human task' });
    const link = within(panel).getByRole('link', { name: 'Record the client’s response' });
    expect(link.getAttribute('href')).toBe('/work/W-1601/respond?task=T-1601');
    expect(within(panel).queryByRole('link', { name: 'Open the decision' })).toBeNull();
    view.unmount();

    const other = render(<WorkItemOverview id="W-1608" item={item('W-1608') as WorkItem} />);
    expect(screen.queryByRole('link', { name: /Record the client|Open the decision/ })).toBeNull();
    other.unmount();

    render(<WorkItemOverview id="W-1201" item={item('W-1201') as WorkItem} />);
    expect(screen.getByRole('link', { name: 'Open the decision' })).toBeTruthy();
  });

  it('a SOW signature task is entered with "Record the client’s signature"', () => {
    render(<WorkItemOverview id="W-1602" item={item('W-1602') as WorkItem} />);
    expect(screen.getByRole('link', { name: 'Record the client’s signature' }).getAttribute('href')).toBe('/work/W-1602/respond?task=T-1602');
  });
});

describe('default form (A-RESPONSE)', () => {
  it('W-1601 shows only the returned options, in board order', async () => {
    await open();
    expect(crumb().textContent).toBe('QUEUE / PREPARE FOR RELEASE / REL-0077 · STATION 3 OF 5');
    expect(screen.getByRole('link', { name: 'QUEUE' }).getAttribute('href')).toBe('/my-work');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Record the client\'s UAT response');
    expect(text()).toContain("Lagoon Health's client contact doesn't log in to PSL Factory");
    const who = screen.getByLabelText('Who responded') as HTMLSelectElement;
    expect([...who.options].map((o) => o.text)).toEqual(['Client contact · Dr Amaka Obi, Lagoon Health']);
    expect(who.value).toBe('P-AO');
    const radios = within(screen.getByRole('radiogroup', { name: 'What they did' })).getAllByRole('radio') as HTMLInputElement[];
    expect(radios.map((r) => r.labels![0].textContent)).toEqual(['Approved', 'Asked for changes', 'Rejected']);
    expect(radios.some((r) => r.checked)).toBe(false);
    const version = screen.getByLabelText('For which version') as HTMLSelectElement;
    expect([...version.options].map((o) => o.text)).toEqual(['Patient app · build 2.4.0 (the version sent for UAT)']);
    expect(screen.queryByLabelText('How they responded')).toBeNull();
    expect(text()).toContain("Signed PDF, e-signature record, or the client's email saved as PDF");
    expect(screen.getByRole('checkbox', { name: 'I confirm this response is genuine and came from the client contact named above.' })).toBeTruthy();
    expect(recordButton('Record response').disabled).toBe(true);
    const aside = screen.getByRole('complementary', { name: 'Tola, PMO agent' });
    expect(aside.querySelector('img')!.getAttribute('src')).toBe('/agents/tola.png');
    expect(aside.textContent).toContain('Tola · PMO agent');
    expect(aside.textContent).toContain("After you record it, I'll check the PDF names build 2.4.0");
    expect(aside.textContent).toContain("I can't record responses for you; a person has to vouch for them.");
    expect(screen.getByLabelText(/^Note/).getAttribute('maxlength')).toBe('2000');
    expect(text()).toContain('0 / 2000');
    expect(text()).not.toContain('SAMPLE');
  });

  it('W-1605 starts the selects on "Choose…" and shows the three channels', async () => {
    await open('W-1605', 'T-1605');
    const who = screen.getByLabelText('Who responded') as HTMLSelectElement;
    expect(who.value).toBe('');
    expect(who.options[0].text).toBe('Choose…');
    expect((screen.getByLabelText('For which version') as HTMLSelectElement).options[0].text).toBe('Choose…');
    const how = screen.getByLabelText('How they responded') as HTMLSelectElement;
    expect([...how.options].map((o) => o.text)).toEqual(['Choose…', 'Email', 'Letter', 'In person']);
  });

  it('offers an action added to the fixture and drops one removed from it; an action without a label is not offered', async () => {
    const added = item('W-1601');
    added.tasks[0].response!.actions = [...added.tasks[0].response!.actions.slice(1), { value: 'signed', label: 'Signed on paper' }, { value: 'input' }];
    answers.item = () => json(200, added);
    await open();
    const labels = within(screen.getByRole('radiogroup', { name: 'What they did' })).getAllByRole('radio').map((r) => (r as HTMLInputElement).labels![0].textContent);
    expect(labels).toEqual(['Asked for changes', 'Rejected', 'Signed on paper']);
  });

  it('never reads /me roles: a persona with other roles sees the same options', async () => {
    answers.me = 'finance_lead';
    await open();
    expect(within(screen.getByRole('radiogroup', { name: 'What they did' })).getAllByRole('radio')).toHaveLength(3);
  });
});

describe('validation (SCR-16-desktop-validation)', () => {
  it('without proof and the tick Record is off with the board line, and pressing it sends nothing', async () => {
    await open();
    await fillW1601({ file: false, attest: false });
    expect(recordButton('Record response').disabled).toBe(true);
    expect(screen.getByRole('alert').textContent).toBe('Add the proof and confirm it’s genuine to record this.');
    expect(text()).toContain('No proof added yet');
    fireEvent.click(recordButton('Record response'));
    expect(writes()).toHaveLength(0);
    await addFile();
    expect(screen.getByRole('alert').textContent).toBe('Add the proof and confirm it’s genuine to record this.');
    tick();
    expect(recordButton('Record response').disabled).toBe(false);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('names only the missing choices: a neutral hint until something changes, then the alert', async () => {
    await open();
    expect(screen.queryByRole('alert')).toBeNull();
    const hint = screen.getByText('Choose when and what they did to record this.');
    expect(hint.className).toContain('resp-alert--hint');
    choose('Approved');
    expect(screen.getByRole('alert').textContent).toBe('Choose when to record this.');
    cleanup();
    await open('W-1605', 'T-1605');
    expect(screen.getByText('Choose who responded, when, what they did, which version and how they responded to record this.').className).toContain('resp-alert--hint');
  });

  it('W-1609 (no case) disables the proof and never enables Record', async () => {
    await open('W-1609', 'T-1609');
    choose('Approved');
    when();
    tick();
    expect(text()).toContain('Proof can’t be uploaded for this item.');
    expect((screen.getByRole('button', { name: 'Add another file' }) as HTMLButtonElement).disabled).toBe(true);
    expect(recordButton('Record response').disabled).toBe(true);
    expect(writes()).toHaveLength(0);
  });
});

describe('proof and the record body', () => {
  it('uploads each file at once with the carried case revision, then records with both ids and the last revision', async () => {
    await open();
    await addFile();
    expect(posts('/evidence')[0]).toMatchObject({ path: '/api/v1/cases/C-1601/evidence', csrf: 'mock-csrf-pm' });
    const first = posts('/evidence')[0].body!;
    expect(first).toEqual({ kind: 'client_response_proof', filename: 'Lagoon_UAT_signoff_11Nov.pdf', content_base64: first.content_base64, case_revision: 4 });
    expect(typeof first.content_base64).toBe('string');
    expect(first.content_base64).not.toContain('data:');
    expect(text()).toContain('Lagoon_UAT_signoff_11Nov.pdf · 184 KB');
    await addFile(pdf('Second_page.pdf', 2048));
    expect(posts('/evidence')[1].body!.case_revision).toBe(5);
    choose('Approved');
    when();
    tick();
    fireEvent.click(recordButton('Record response'));
    await screen.findByRole('status');
    expect(posts('/response')[0].body).toMatchObject({ evidence_id: 'EV-C-1601-1', evidence_ids: ['EV-C-1601-2'], case_revision: 6 });
  });

  it('removing a file only drops it from what is sent', async () => {
    await open();
    await addFile();
    await addFile(pdf('Wrong.pdf', 1024));
    fireEvent.click(screen.getByRole('button', { name: 'Remove Wrong.pdf' }));
    expect(text()).not.toContain('Wrong.pdf');
    choose('Approved');
    when();
    tick();
    fireEvent.click(recordButton('Record response'));
    await screen.findByRole('status');
    const body = posts('/response')[0].body!;
    expect(body.evidence_id).toBe('EV-C-1601-1');
    expect(body).not.toHaveProperty('evidence_ids');
  });

  it('sends exactly the board body once, with CSRF, and a typed note', async () => {
    await open();
    await fillW1601();
    fireEvent.click(recordButton('Record response'));
    await screen.findByRole('status');
    expect(posts('/response')).toEqual([
      {
        method: 'POST',
        path: '/api/v1/tasks/T-1601/response',
        csrf: 'mock-csrf-pm',
        body: { expected_revision: 2, who: 'P-AO', action: 'approved', responded_at: '2026-11-11T16:20:00+01:00', evidence_id: 'EV-C-1601-1', attested: true, case_revision: 5, version_id: 'V-240', received_via: 'email' },
      },
    ]);
    expect(posts('/claim')).toHaveLength(0);
  });

  it('adds a trimmed note when one is typed', async () => {
    await open();
    await fillW1601();
    fireEvent.change(screen.getByLabelText(/^Note/), { target: { value: '  Signed on paper ' } });
    expect(text()).toContain('18 / 2000');
    fireEvent.click(recordButton('Record response'));
    await screen.findByRole('status');
    expect(posts('/response')[0].body).toMatchObject({ note: 'Signed on paper' });
    for (const key of ['team', 'what', 'estimate_person_days']) expect(posts('/response')[0].body).not.toHaveProperty(key);
  });

  it('upload errors stay on the chip; Try again reloads before it uploads and is never pressed for you', async () => {
    answers.upload = (n, c) =>
      n === 0 ? json(503, { code: 'server_error', message: 'Down.' }) : n === 1 ? json(409, STALE) : json(200, { evidence_id: `EV-${n}`, sha256: 'a'.repeat(64), case_revision: (c.body!.case_revision as number) + 1 });
    await open();
    fireEvent.change(fileInput(), { target: { files: [pdf()] } });
    await screen.findByText('Couldn’t upload. Try again.');
    expect(posts('/evidence')).toHaveLength(1);
    const getsBefore = gets();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByText('This item changed. Add the file again.');
    expect(gets()).toBe(getsBefore + 2); // the Try again reload, then the 409 reload
    expect(posts('/evidence')).toHaveLength(2);
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
    expect(recordButton('Record response').disabled).toBe(true);
  });

  it('a 403 upload says so on the chip and a 422 shows the server message', async () => {
    answers.upload = (n) => (n === 0 ? json(403, FORBIDDEN) : json(422, { code: 'invalid', message: 'Check these fields: kind.' }));
    await open();
    fireEvent.change(fileInput(), { target: { files: [pdf()] } });
    await screen.findByText('You can’t add proof to this item.');
    fireEvent.change(fileInput(), { target: { files: [pdf('b.pdf', 10)] } });
    await screen.findByText('Check these fields: kind.');
  });
});

describe('claim, one write at a time', () => {
  it('W-1605 claims first and records with the claim’s revision; a 409 claim records nothing', async () => {
    await open('W-1605', 'T-1605');
    fireEvent.change(screen.getByLabelText('Who responded'), { target: { value: 'P-SO' } });
    fireEvent.change(screen.getByLabelText('For which version'), { target: { value: 'V-311' } });
    fireEvent.change(screen.getByLabelText('How they responded'), { target: { value: 'letter' } });
    choose('Asked for changes');
    when();
    await addFile();
    tick();
    fireEvent.click(recordButton('Record response'));
    await screen.findByRole('status');
    const order = writes().map((c) => c.path);
    expect(order).toEqual(['/api/v1/cases/C-1605/evidence', '/api/v1/tasks/T-1605/claim', '/api/v1/tasks/T-1605/response']);
    expect(posts('/claim')[0].body).toEqual({ expected_revision: 3 });
    expect(posts('/response')[0].body).toMatchObject({ expected_revision: 4, who: 'P-SO', action: 'changes_requested', version_id: 'V-311', received_via: 'letter' });
  });

  it('a claim 409 sends no response and shows the stale warning', async () => {
    answers.claim = () => json(409, STALE);
    await open('W-1605', 'T-1605');
    fireEvent.change(screen.getByLabelText('Who responded'), { target: { value: 'P-KA' } });
    fireEvent.change(screen.getByLabelText('For which version'), { target: { value: 'V-310' } });
    fireEvent.change(screen.getByLabelText('How they responded'), { target: { value: 'email' } });
    choose('Approved');
    when();
    await addFile();
    tick();
    fireEvent.click(recordButton('Record response'));
    await screen.findByText(/This changed while you were recording/);
    expect(posts('/response')).toHaveLength(0);
  });

  it('a claim network error warns and leaves the response unsent', async () => {
    answers.claim = () => Promise.reject(new TypeError('Failed to fetch'));
    await open('W-1605', 'T-1605');
    fireEvent.change(screen.getByLabelText('Who responded'), { target: { value: 'P-KA' } });
    fireEvent.change(screen.getByLabelText('For which version'), { target: { value: 'V-310' } });
    fireEvent.change(screen.getByLabelText('How they responded'), { target: { value: 'email' } });
    choose('Approved');
    when();
    await addFile();
    tick();
    fireEvent.click(recordButton('Record response'));
    await screen.findByText('We couldn’t get this ready. Try again.');
    expect(posts('/response')).toHaveLength(0);
    expect(recordButton('Record response').disabled).toBe(false);
  });

  it('a double press with a deferred reply sends one response; meanwhile Record reads "Recording…" and the form is busy', async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    answers.respond = async (_, c) => {
      await gate;
      return json(200, recordedReply(c.body!));
    };
    await open();
    await fillW1601();
    const button = recordButton('Record response');
    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(() => expect(recordButton('Recording…').disabled).toBe(true));
    expect(document.querySelector('form')!.getAttribute('aria-busy')).toBe('true');
    fireEvent.click(recordButton('Recording…'));
    await act(async () => release());
    await screen.findByRole('status');
    expect(posts('/response')).toHaveLength(1);
  });
});

describe('success (SCR-16-desktop-success)', () => {
  it('shows what was recorded and what happens next, with no form controls', async () => {
    await open();
    await fillW1601();
    fireEvent.click(recordButton('Record response'));
    const status = await screen.findByRole('status');
    expect(text()).toContain('REL-0077 · LAGOON HEALTH');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Client UAT response');
    expect(status.textContent).toBe('Response recorded. Client UAT sign-off for Lagoon Health, received by email on 11 Nov, recorded by Tunde Bello at 15:04 with 1 proof file.');
    expect(text()).toContain('What happens next');
    expect(text()).toContain('The release line moves on to go-live readiness.');
    expect(text()).toContain('Milestone 2 can now be marked complete, which lets Chidi draft its invoice.');
    expect(text()).toContain('Recorded responses can’t be edited. If something is wrong, record a correction; both stay in the history.');
    expect(screen.getByRole('link', { name: 'Back to the work item' }).getAttribute('href')).toBe('/work/W-1601');
    expect(document.querySelectorAll('main input, main select, main textarea')).toHaveLength(0);
    await waitFor(() => expect(gets()).toBe(2)); // one reload after the 200
  });

  it('on the phone it shows "← Work item", the reference and "Back to my queue"', async () => {
    phone();
    await open();
    choose('Approved');
    when();
    await addFile();
    tick();
    fireEvent.click(recordButton('Record response'));
    await screen.findByRole('status');
    await expectPhoneBack('Work item', '/work/W-1601');
    expect(screen.getByText('REL-0077').className).toContain('resp-phoneref');
    expect(screen.getByRole('link', { name: 'Back to my queue' }).getAttribute('href')).toBe('/my-work');
  });

  it('a task that is already recorded opens on the success view', async () => {
    answers.item = () => json(200, item('W-1601.recorded'));
    await open();
    expect(screen.getByRole('status').textContent).toMatch(/^Response recorded\. Client UAT sign-off for Lagoon Health, received by email on 11 Nov, recorded by Tunde Bello at \d\d:\d\d with 1 proof file\.$/);
    // The same eyebrow and heading as the view right after Record.
    expect(text()).toContain('REL-0077 · LAGOON HEALTH');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Client UAT response');
  });

  it('reopened with two responders it leaves the organisation out; the SOW keeps its station', async () => {
    answers.item = () => json(200, item('W-1605.recorded'));
    await open('W-1605', 'T-1605');
    expect(document.querySelector('.resp-eyebrow')!.textContent).toBe(item('W-1605').reference.toUpperCase());
    cleanup();
    answers.item = () => json(200, item('W-1602.recorded'));
    await open('W-1602', 'T-1602');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('SOW signature');
    expect(text()).toContain('SOW-0207 · TAMARIND LOANS');
  });
});

describe('absent fields are left out (W-1606)', () => {
  const BOARD = ["Lagoon Health's client contact", 'Signed PDF', 'After you record it', 'Lagoon Health'];

  it('the form has no intro, aside or proof hint, and no board copy', async () => {
    await open('W-1606', 'T-1606');
    expect(crumb().textContent).toBe('QUEUE / PREPARE FOR RELEASE / REL-0083 · STATION 3 OF 5');
    expect(screen.queryByRole('complementary')).toBeNull();
    expect(document.querySelector('.resp-intro')).toBeNull();
    expect(document.querySelector('.resp-drop .psl-hint')).toBeNull();
    expect(screen.getByLabelText('Who responded')).toBeTruthy();
    expect(screen.getByRole('radiogroup', { name: 'What they did' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Add another file' })).toBeTruthy();
    expect(screen.getByRole('checkbox')).toBeTruthy();
    for (const s of BOARD) expect(text()).not.toContain(s);
  });

  it('the success view uses the reload’s recorded when the 200 has none, and adds nothing else', async () => {
    const recorded = item('W-1606.recorded');
    recorded.tasks[0].response!.recorded = { by: { name: 'Tunde Bello' }, at: '2026-11-11T14:04:00Z' };
    answers.item = (n) => json(200, n === 0 ? item('W-1606') : recorded);
    answers.respond = () => json(200, { task_id: 'T-1606', work_state: 'ready' });
    await open('W-1606', 'T-1606');
    choose('Approved');
    when();
    await addFile();
    tick();
    fireEvent.click(recordButton('Record response'));
    await waitFor(() => expect(screen.getByRole('status').textContent).toBe('Response recorded. Recorded by Tunde Bello at 15:04.'));
    expect(text()).not.toContain('received by');
    expect(text()).not.toContain('proof file');
    expect(text()).not.toContain('What happens next');
    for (const s of BOARD) expect(text()).not.toContain(s);
  });
});

describe('SOW signature (SCR-16-desktop-sow-signed)', () => {
  it('W-1602 shows the project crumb, the Signature panel and what happens next', async () => {
    await open('W-1602', 'T-1602');
    const trail = crumb();
    expect(trail.textContent).toBe('PROJECTS / TAMARIND LOANS / DOCUMENTS / SOW-0207');
    expect(within(trail).getAllByRole('link').map((a) => [a.textContent, a.getAttribute('href')])).toEqual([['PROJECTS', '/projects']]);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Record the client\'s SOW signature');
    expect(screen.getByRole('heading', { level: 2, name: 'Signature' })).toBeTruthy();
    expect(text()).toContain('SOW-0207 v1 · Tamarind Loans · sent 18 Dec 10:30');
    expect(text()).toContain('The version the client received');
    expect(text()).toContain('Ngozi Bello · Head of Lending Operations, Tamarind Loans');
    const radios = within(screen.getByRole('radiogroup', { name: 'What they did' })).getAllByRole('radio') as HTMLInputElement[];
    expect(radios.map((r) => r.labels![0].textContent)).toEqual(['Signed', 'Asked for changes', 'Declined']);
    expect(text()).toContain("What happens next: the SOW's 4 stages become the project's milestones, each billable once it's complete. Delivery starts with release gates.");
    expect(recordButton('Record signature')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Choose the signed copy' })).toBeTruthy();
    expect(screen.getByRole('complementary', { name: 'About this signature' }).textContent).toContain("The client doesn't log in.");
  });

  it('records "Declined" as rejected', async () => {
    await open('W-1602', 'T-1602');
    choose('Declined');
    when('2026-12-20T14:10', 'When');
    await addFile(pdf('SOW-0207-v1-signed.pdf', 1153434));
    expect(text()).toContain('SOW-0207-v1-signed.pdf');
    expect(text()).toContain('Uploaded · 1.1 MB');
    tick();
    fireEvent.click(recordButton('Record signature'));
    await screen.findByRole('status');
    expect(posts('/response')[0].body).toMatchObject({ who: 'P-NB', action: 'rejected', version_id: 'SOW-0207-v1', responded_at: '2026-12-20T14:10:00+01:00', case_revision: 4 });
  });

  it('on the phone the heading is the station and the back link the document', async () => {
    phone();
    await open('W-1602', 'T-1602');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('SOW signature');
    await expectPhoneBack('SOW', '/work/W-1602');
    expect(screen.getByText('SOW-0207').className).toContain('resp-phoneref');
    expect(screen.queryByRole('complementary')).toBeNull();
  });

  it('on the phone the client form collapses the single options into one line', async () => {
    phone();
    await open();
    await expectPhoneBack('Queue', '/my-work');
    expect(text()).toContain('Lagoon Health · Patient app · build 2.4.0 · Dr Amaka Obi');
    expect(screen.queryByLabelText('Who responded')).toBeNull();
    expect(screen.getByLabelText('When they responded')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Take a photo or choose a file' })).toBeTruthy();
    expect(fileInput().hasAttribute('capture')).toBe(false);
    expect(screen.getByRole('checkbox', { name: 'I confirm this response is genuine.' })).toBeTruthy();
    expect(text()).not.toContain("Lagoon Health's client contact");
    expect(screen.queryByRole('complementary')).toBeNull();
  });
});

describe('errors on record', () => {
  it('422 shows the server message above Record, keeps the entries and sends nothing more', async () => {
    answers.respond = () => json(422, { code: 'invalid', message: 'Check these fields: evidence_id.' });
    await open();
    await fillW1601();
    fireEvent.click(recordButton('Record response'));
    await screen.findByText('Check these fields: evidence_id.');
    expect(screen.getByText('Check these fields: evidence_id.').closest('.psl-callout')!.className).toContain('psl-callout--problem');
    expect((screen.getByRole('radio', { name: 'Approved' }) as HTMLInputElement).checked).toBe(true);
    expect(text()).toContain('Lagoon_UAT_signoff_11Nov.pdf');
    expect(posts('/response')).toHaveLength(1);
  });

  it('409 reloads once, keeps entries and proof, and sends nothing more', async () => {
    answers.respond = () => json(409, STALE);
    await open();
    await fillW1601();
    fireEvent.click(recordButton('Record response'));
    await screen.findByText('This changed while you were recording. We’ve reloaded it. Check the details and record again.');
    expect(gets()).toBe(2);
    expect((screen.getByRole('radio', { name: 'Approved' }) as HTMLInputElement).checked).toBe(true);
    expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(true);
    expect(text()).toContain('Lagoon_UAT_signoff_11Nov.pdf · 184 KB');
    expect(posts('/response')).toHaveLength(1);
  });

  it('after a 409 the next press carries the reloaded item’s case revision, not the last upload’s', async () => {
    const moved = { ...item('W-1601'), case_revision: 7 };
    answers.item = (n) => json(200, n === 0 ? item('W-1601') : moved);
    answers.respond = (n, c) => (n === 0 ? json(409, STALE) : json(200, recordedReply(c.body!)));
    await open();
    await fillW1601();
    fireEvent.click(recordButton('Record response'));
    await screen.findByText(/This changed while you were recording/);
    expect(posts('/response')[0].body!.case_revision).toBe(5);
    fireEvent.click(recordButton('Record response'));
    await screen.findByRole('status');
    expect(posts('/response')).toHaveLength(2);
    expect(posts('/response')[1].body).toMatchObject({ evidence_id: 'EV-C-1601-1', case_revision: 7 });
  });

  it('409 clears a choice the reloaded task no longer offers', async () => {
    const changed = item('W-1601');
    changed.tasks[0].response!.actions = changed.tasks[0].response!.actions.filter((a) => a.value !== 'approved');
    answers.item = (n) => json(200, n === 0 ? item('W-1601') : changed);
    answers.respond = () => json(409, STALE);
    await open();
    await fillW1601();
    fireEvent.click(recordButton('Record response'));
    await screen.findByText(/This changed while you were recording/);
    expect(screen.queryByRole('radio', { name: 'Approved' })).toBeNull();
    expect(recordButton('Record response').disabled).toBe(true);
  });

  it('409 whose reload is already recorded shows the success view', async () => {
    answers.item = (n) => json(200, item(n === 0 ? 'W-1601' : 'W-1601.recorded'));
    answers.respond = () => json(409, STALE);
    await open();
    await fillW1601();
    fireEvent.click(recordButton('Record response'));
    await screen.findByRole('status');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Client UAT response');
  });

  it('403 reloads once; W-1608 after the reload is not open here', async () => {
    answers.item = (n) => json(200, item(n === 0 ? 'W-1601' : 'W-1608'));
    answers.respond = () => json(403, FORBIDDEN);
    await open();
    await fillW1601();
    fireEvent.click(recordButton('Record response'));
    await screen.findByText('This response isn’t open here');
    expect(gets()).toBe(2);
    expect(screen.getByRole('link', { name: 'Open the work item' }).getAttribute('href')).toBe('/work/W-1601');
    expect(posts('/response')).toHaveLength(1);
  });

  it('403 on a task still open shows the server message and keeps the controls', async () => {
    answers.respond = () => json(403, FORBIDDEN);
    await open();
    await fillW1601();
    fireEvent.click(recordButton('Record response'));
    await screen.findByText('Your role does not allow this.');
    expect(recordButton('Record response').disabled).toBe(false);
  });

  it('401 shows the sign-in link back to this form', async () => {
    answers.respond = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open();
    await fillW1601();
    fireEvent.click(recordButton('Record response'));
    const link = await screen.findByRole('link', { name: 'Sign in' });
    expect(new URL(link.getAttribute('href')!, 'http://x').searchParams.get('next')).toBe('/work/W-1601/respond?task=T-1601');
  });

  it('item 404 shows no access without the id or title, and 500 the error card with Try again', async () => {
    answers.item = () => json(404, { code: 'not_found', message: 'We could not find that record.' });
    const view = render(
      <AppShell>
        <ResponseView id="W-1601" taskId="T-1601" />
      </AppShell>,
    );
    await screen.findByText('You can’t open this work item');
    expect(text()).not.toContain('W-1601');
    expect(text()).not.toContain('Lagoon');
    view.unmount();
    answers.item = (n) => (n < 2 ? json(500, { code: 'server_error', message: 'Down.' }) : json(200, item('W-1601')));
    await open();
    expect(text()).toContain('We couldn’t load this response form. Your work is safe; nothing was changed.');
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByRole('heading', { level: 1 });
  });

  it('the not-open state for an unknown task, a task without response, and a variant this page does not record', async () => {
    await open('W-1601', 'T-9999');
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('This response isn’t open here');
    expect(text()).toContain('It may have been recorded already or moved. The work item shows where things stand.');
    for (const [id, task] of [
      ['W-1201', 'T-1201'],
      ['W-1608', 'T-1608'],
    ]) {
      document.body.innerHTML = '';
      await open(id, task);
      expect(text()).toContain('This response isn’t open here');
    }
    const team = item('W-1601');
    team.tasks[0].response!.variant = 'team_input';
    answers.item = () => json(200, team);
    document.body.innerHTML = '';
    await open();
    expect(text()).toContain('This response isn’t open here');
    expect(writes()).toHaveLength(0);
  });
});

describe('uncertain effect: re-read, never resend', () => {
  it('a network error whose reload is recorded shows the warning and the success view, with one POST', async () => {
    answers.respond = () => Promise.reject(new TypeError('Failed to fetch'));
    answers.item = (n) => json(200, item(n === 0 ? 'W-1601' : 'W-1601.recorded'));
    await open();
    await fillW1601();
    fireEvent.click(recordButton('Record response'));
    await screen.findByRole('status');
    expect(text()).toContain('We couldn’t confirm your response was recorded. We’ve reloaded this item so you can see whether it was.');
    expect(posts('/response')).toHaveLength(1);
  });

  it('a reload that still shows the open task brings Record back for a deliberate press, without sending', async () => {
    answers.respond = (n) => (n === 0 ? json(502, { code: 'bad_gateway', message: 'Bad gateway.' }) : json(200, recordedReply({})));
    await open();
    await fillW1601();
    fireEvent.click(recordButton('Record response'));
    await screen.findByText(/We couldn’t confirm your response was recorded/);
    await waitFor(() => expect(recordButton('Record response').disabled).toBe(false));
    expect(posts('/response')).toHaveLength(1);
    expect(gets()).toBe(2);
  });

  it('when the reload fails too, Record stays off and Try again only reads', async () => {
    answers.respond = () => Promise.reject(new TypeError('Failed to fetch'));
    answers.item = (n) => (n === 0 ? json(200, item('W-1601')) : n === 1 ? json(503, { code: 'down', message: 'Down.' }) : json(200, item('W-1601.recorded')));
    await open();
    await fillW1601();
    fireEvent.click(recordButton('Record response'));
    await screen.findByText(/couldn’t reload to check\. Record stays off\./);
    expect(recordButton('Record response').disabled).toBe(true);
    const before = writes().length;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByRole('status');
    expect(writes()).toHaveLength(before);
    expect(gets()).toBe(3);
  });
});

describe('reconcile panel (A-RECONCILE)', () => {
  it('on the phone the pinned button is pressable before a choice: a press asks for one and sends nothing', async () => {
    phone();
    answers.me = 'finance_lead';
    await openWork('W-1603');
    const go = screen.getByRole('button', { name: 'Record and continue' }) as HTMLButtonElement;
    expect(go.disabled).toBe(false);
    expect(screen.queryByText('Choose what happened to continue.')).toBeNull();
    fireEvent.click(go);
    expect(screen.getByRole('alert').textContent).toBe('Choose what happened to continue.');
    expect(document.activeElement).toBe(screen.getAllByRole('radio')[0]);
    expect(writes()).toHaveLength(0);
    fireEvent.click(screen.getByRole('radio', { name: /It didn’t arrive/ }));
    expect(screen.queryByText('Choose what happened to continue.')).toBeNull();
    fireEvent.click(go);
    await waitFor(() => expect(posts('/actions')).toHaveLength(1));
  });

  it('W-1603 shows the checks, the three outcomes with the API’s notes and the button', async () => {
    answers.me = 'finance_lead';
    await openWork('W-1603');
    const panel = screen.getByRole('complementary', { name: 'Confirm what happened' });
    expect(within(panel).getByRole('heading', { level: 2 }).textContent).toBe('Confirm what happened');
    expect(panel.textContent).toContain('Chidi checked 6 times over 2 hours and found no delivery receipt. The factory won’t resend until a person confirms what happened, so the client is never invoiced twice.');
    const options = within(within(panel).getByRole('radiogroup', { name: 'Confirm what happened' })).getAllByRole('radio') as HTMLInputElement[];
    expect(options.map((o) => o.labels![0].textContent)).toEqual([
      'It arrived. I have proof the client received it (upload it next).',
      'It didn’t arrive. Allow one resend of the same version.',
      'I can’t tell yet. Keep it held and remind me tomorrow.',
    ]);
    expect(within(panel).getByRole('button', { name: 'Record and continue' })).toBeTruthy();
    expect(panel.textContent).toContain('Your choice is recorded with your name. A resend reuses the same invoice number.');
    expect(panel.closest('.work-column')!.parentElement!.className).toBe('work-columns');
  });

  it('on the phone it shows the warning callout instead', async () => {
    phone();
    answers.me = 'finance_lead';
    await openWork('W-1603');
    expect(text()).toContain('No receipt found after 6 checks. Confirm what happened before anything is resent.');
  });

  it('W-1607 shows only two outcomes and no notes', async () => {
    answers.me = 'finance_lead';
    await openWork('W-1607');
    const panel = screen.getByRole('complementary', { name: 'Confirm what happened' });
    expect(within(panel).getAllByRole('radio').map((o) => (o as HTMLInputElement).labels![0].textContent)).toEqual(['It didn’t arrive.', 'I can’t tell yet.']);
    expect(panel.textContent).not.toContain('Allow');
    expect(panel.textContent).toContain('Chidi checked'.replace('Chidi', 'The factory') + ' 3 times and found no delivery receipt.');
    expect(panel.textContent).toContain('Your choice is recorded with your name.');
    expect(panel.textContent).not.toContain('invoice number');
  });

  it('W-1604 (no grant) and W-1601 show no panel and send nothing', async () => {
    answers.me = 'finance_lead';
    await openWork('W-1604');
    expect(screen.queryByText('Confirm what happened')).toBeNull();
    document.body.innerHTML = '';
    await openWork('W-1601');
    expect(screen.queryByText('Confirm what happened')).toBeNull();
    expect(writes()).toHaveLength(0);
  });

  it('"It arrived" needs the delivery receipt uploaded, then sends one reconcile and reloads the page once', async () => {
    answers.me = 'finance_lead';
    await openWork('W-1603');
    const record = () => screen.getByRole('button', { name: /Record and continue|Recording…/ }) as HTMLButtonElement;
    expect(record().disabled).toBe(true);
    choose('It arrived. I have proof the client received it (upload it next).');
    expect(record().disabled).toBe(true);
    await addFile(pdf('receipt.pdf', 4096));
    expect(posts('/evidence')[0]).toMatchObject({ path: '/api/v1/cases/C-1603/evidence', body: { kind: 'delivery_receipt', case_revision: 5 }, csrf: 'mock-csrf-finance_lead' });
    expect(record().disabled).toBe(false);
    fireEvent.click(record());
    fireEvent.click(record());
    await screen.findByText('Recorded. Reloading the work item…');
    expect(posts('/actions')).toEqual([
      { method: 'POST', path: '/api/v1/work/W-1603/actions', csrf: 'mock-csrf-finance_lead', body: { expected_revision: 6, action: 'reconcile', outcome: 'delivered', evidence_id: 'EV-C-1603-1', case_revision: 6 } },
    ]);
    expect(reloadPage).toHaveBeenCalledTimes(1);
  });

  it('"It didn’t arrive" sends no evidence', async () => {
    answers.me = 'finance_lead';
    await openWork('W-1603');
    choose('It didn’t arrive. Allow one resend of the same version.');
    fireEvent.click(screen.getByRole('button', { name: 'Record and continue' }));
    await screen.findByText('Recorded. Reloading the work item…');
    expect(posts('/actions')[0].body).toEqual({ expected_revision: 6, action: 'reconcile', outcome: 'not_delivered' });
    expect(writes()).toHaveLength(1);
  });

  it('409 and a network error warn with "Reload the work item" and send nothing more', async () => {
    answers.me = 'finance_lead';
    answers.action = (n) => (n === 0 ? json(409, STALE) : Promise.reject(new TypeError('Failed to fetch')));
    await openWork('W-1603');
    choose('I can’t tell yet. Keep it held and remind me tomorrow.');
    fireEvent.click(screen.getByRole('button', { name: 'Record and continue' }));
    await screen.findByText('This item changed. Reload it to see the latest.');
    expect((screen.getByRole('button', { name: 'Record and continue' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Reload the work item' }));
    expect(reloadPage).toHaveBeenCalledTimes(1);
    expect(posts('/actions')).toHaveLength(1);
  });

  it('a network error says the answer is unconfirmed', async () => {
    answers.me = 'finance_lead';
    answers.action = () => Promise.reject(new TypeError('Failed to fetch'));
    await openWork('W-1603');
    choose('I can’t tell yet. Keep it held and remind me tomorrow.');
    fireEvent.click(screen.getByRole('button', { name: 'Record and continue' }));
    await screen.findByText('We couldn’t confirm your answer. Reload the work item to see whether it was recorded.');
    expect(posts('/actions')).toHaveLength(1);
    expect(reloadPage).not.toHaveBeenCalled();
  });

  it('403 and 422 show the server message in the panel; 401 the sign-in link', async () => {
    answers.me = 'finance_lead';
    answers.action = (n) =>
      n === 0 ? json(403, FORBIDDEN) : n === 1 ? json(422, { code: 'invalid', message: 'Check these fields: outcome.' }) : json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await openWork('W-1603');
    choose('I can’t tell yet. Keep it held and remind me tomorrow.');
    fireEvent.click(screen.getByRole('button', { name: 'Record and continue' }));
    await screen.findByText('Your role does not allow this.');
    fireEvent.click(screen.getByRole('button', { name: 'Record and continue' }));
    await screen.findByText('Check these fields: outcome.');
    fireEvent.click(screen.getByRole('button', { name: 'Record and continue' }));
    const link = await screen.findByRole('link', { name: 'Sign in' });
    expect(new URL(link.getAttribute('href')!, 'http://x').searchParams.get('next')).toBe('/work/W-1603');
  });
});

describe('boundaries', () => {
  const root = join(__dirname, '..');
  const grep = (pattern: string, path: string) => {
    try {
      return execFileSync('grep', ['-rn', pattern, path], { cwd: root, encoding: 'utf8' });
    } catch {
      return '';
    }
  };

  it('no feature branch reads /me roles or destinations, and the only casts are in api.ts', () => {
    expect(grep('roles\\|destinations', 'src/features/response')).toBe('');
    const casts = grep(' as unknown as\\| as Response', 'src/features/response').split('\n').filter(Boolean);
    expect(casts.length).toBeGreaterThan(0);
    expect(casts.every((line) => line.startsWith('src/features/response/api.ts:'))).toBe(true);
    expect(grep('resend\\|deliver', 'src/features/response/api.ts')).toBe('');
  });
});
