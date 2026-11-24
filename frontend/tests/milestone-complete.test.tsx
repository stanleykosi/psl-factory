// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MilestoneCompletePage } from '@/features/projects/MilestoneComplete';
import { AppShell } from '@/shell/AppShell';

import { bellFeed, isBellFeed, isRoleDashboard, roleDashboard } from './bell-feed';

vi.mock('next/navigation', () => ({ usePathname: () => '/projects/P-0101/milestones/complete', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }), useSearchParams: () => new URLSearchParams() }));

const me = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/me.pm.json'), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const CASE = '00000000-0000-4000-8000-000000000101';
const NAME = 'UAT sign-off';
const OPTIONS = { revision: 5, proofs: [{ id: 31, label: 'Completion evidence · version 2' }, { id: 29, label: 'Completion evidence · version 1' }], next_page: null, can_complete: true, can_attach_pdf: true, hold: null };
const RECORDED = { id: 412, revision: 6, name: NAME, evidence_id: 31 };
const REREAD = { id: 412, name: NAME, completed_at: '2026-11-23T10:15:00Z', evidence_id: 31, proof_version: 3 };

type Req = { method: string; path: string; search: string; body: string };
let log: Req[];
let optionsBody: unknown;
let onPost: () => Response | Promise<Response>;
let onReread: () => Response | Promise<Response>;
let onFile: () => Response;

beforeEach(() => {
  log = [];
  optionsBody = OPTIONS;
  onPost = () => json(201, RECORDED);
  onReread = () => json(200, REREAD);
  onFile = () => json(200, { upload_id: 88, name: 'signoff.pdf', size: 2048, sha256: 'a'.repeat(64), download_url: '/x' });
  vi.useRealTimers();
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: Request) => {
      if (isBellFeed(input)) return bellFeed();
      if (isRoleDashboard(input)) return roleDashboard();
      const url = new URL(input.url);
      if (url.pathname === '/api/v1/me') return json(200, me);
      const body = input.method === 'POST' && !url.pathname.endsWith('/files') ? await input.clone().text() : '';
      log.push({ method: input.method, path: url.pathname.replace(CASE, 'CASE'), search: url.search, body });
      if (url.pathname.endsWith('/files')) return onFile();
      if (url.pathname.endsWith('/milestones/completions')) return input.method === 'POST' ? onPost() : typeof optionsBody === 'function' ? (optionsBody as () => Response)() : json(200, optionsBody);
      if (/\/milestones\/\d+$/.test(url.pathname)) return onReread();
      return json(404, { code: 'not_found', message: 'x' });
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function until(check: () => void, ms = 3000) {
  const end = Date.now() + ms;
  for (;;) {
    try {
      check();
      return;
    } catch (error) {
      if (Date.now() > end) throw error;
    }
    await act(async () => {
      await new Promise((r) => setTimeout(r, 5));
    });
  }
}
const text = () => document.body.textContent ?? '';
const button = () => screen.queryByRole('button', { name: 'Mark complete' }) as HTMLButtonElement | null;
const posts = () => log.filter((r) => r.method === 'POST' && r.path.endsWith('/milestones/completions'));
const optionReads = () => log.filter((r) => r.method === 'GET' && r.path.endsWith('/milestones/completions'));

async function open(name: string | null = NAME) {
  render(
    <AppShell>
      <MilestoneCompletePage caseId={CASE} name={name} />
    </AppShell>,
  );
  if (name === null || name.trim() === '' || name.length > 200) {
    await until(() => expect(text()).toContain('Choose a milestone from the Milestones tab.'));
    return;
  }
  await until(() => expect(optionReads().length).toBeGreaterThan(0));
  await until(() => expect(text()).toContain('Milestone'));
  await act(async () => {});
}
const pickProof = () => fireEvent.click(screen.getByLabelText('Completion evidence · version 2'));
const confirmBox = () => fireEvent.click(screen.getByLabelText('I confirm this milestone is complete as the SOW describes it.'));
const ready = async () => {
  await open();
  await until(() => expect(button()).not.toBeNull());
  pickProof();
  confirmBox();
};

describe('control follows the server', () => {
  it('can_complete true shows the control; false shows none, whatever the persona', async () => {
    await open();
    expect(button()).not.toBeNull();
    cleanup();
    optionsBody = { ...OPTIONS, can_complete: false };
    await open();
    expect(button()).toBeNull();
    expect(text()).toContain('You can’t mark this milestone complete.');
  });

  it.each([
    ['baseline_required', 'This project has no signed baseline yet.'],
    ['proof_required', 'There is no proof on record for this milestone yet.'],
    ['name_in_use', 'A completion with this name is already recorded.'],
  ])('hold %s shows words and no control', async (hold, words) => {
    optionsBody = { ...OPTIONS, can_complete: false, hold };
    await open();
    expect(text()).toContain(words);
    expect(text()).not.toContain(hold);
    expect(button()).toBeNull();
  });

  it('the button is disabled until a proof and the confirmation are there', async () => {
    await open();
    expect(button()!.disabled).toBe(true);
    pickProof();
    expect(button()!.disabled).toBe(true);
    confirmBox();
    expect(button()!.disabled).toBe(false);
  });

  it('no name, or one over 200 characters, makes no request', async () => {
    await open(null);
    cleanup();
    await open('x'.repeat(201));
    expect(log).toHaveLength(0);
  });
});

describe('the write and the re-read', () => {
  it('one press is one POST with the exact body; recorded shows from the re-read', async () => {
    await ready();
    fireEvent.click(button()!);
    await until(() => expect(text()).toContain('Milestone recorded'));
    expect(posts()).toHaveLength(1);
    expect(JSON.parse(posts()[0].body)).toEqual({ revision: 5, name: NAME, evidence_id: 31 });
    expect(text()).toContain('Proof version 3');
    expect(text()).not.toMatch(/start the invoice|chidi|invoice started/i);
    expect(log.every((r) => !/billing|work/.test(r.path))).toBe(true);
  });

  it('double activation sends one POST; "Checking the record…" shows before the re-read answers', async () => {
    let release: () => void = () => {};
    onReread = () => new Promise<Response>((resolve) => (release = () => resolve(json(200, REREAD))));
    await ready();
    fireEvent.click(button()!);
    fireEvent.click(button()!);
    await until(() => expect(text()).toContain('Checking the record…'));
    expect(text()).not.toContain('Milestone recorded');
    expect(posts()).toHaveLength(1);
    release();
    await until(() => expect(text()).toContain('Milestone recorded'));
  });

  it('a re-read that fails never says recorded; Check again only reads', async () => {
    let fail = true;
    onReread = () => (fail ? json(503, { code: 'server_error', message: 'x' }) : json(200, REREAD));
    await ready();
    fireEvent.click(button()!);
    await until(() => expect(text()).toContain('couldn’t confirm it yet'));
    expect(text()).not.toContain('Milestone recorded');
    expect(button()).toBeNull();
    fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'Check again' }));
    await until(() => expect(text()).toContain('Milestone recorded'));
    expect(posts()).toHaveLength(1);
  });

  it('a re-read that names another milestone is not shown as recorded', async () => {
    onReread = () => json(200, { ...REREAD, name: 'Other' });
    await ready();
    fireEvent.click(button()!);
    await until(() => expect(text()).toContain('couldn’t confirm it yet'));
    expect(text()).not.toContain('Milestone recorded');
  });

  it('the recorded view takes name, date and version from the re-read', async () => {
    onPost = () => json(201, { ...RECORDED, evidence_id: 99 });
    await ready();
    fireEvent.click(button()!);
    await until(() => expect(text()).toContain('Proof version 3'));
  });

  it('a PDF uploads first, needs the second tick, then posts upload_id and checked', async () => {
    await open();
    await until(() => expect(screen.getByLabelText(/Evidence file|Choose a file/i, { selector: 'input' })).toBeTruthy());
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(['%PDF'], 'signoff.pdf', { type: 'application/pdf' })] } });
    await until(() => expect(text()).toContain('signoff.pdf'));
    confirmBox();
    expect(button()!.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('I have checked this file is the proof for this milestone.'));
    expect(button()!.disabled).toBe(false);
    fireEvent.click(button()!);
    await until(() => expect(posts()).toHaveLength(1));
    expect(JSON.parse(posts()[0].body)).toEqual({ revision: 5, name: NAME, upload_id: 88, checked: true });
    expect(log.findIndex((r) => r.path.endsWith('/files'))).toBeLessThan(log.findIndex((r) => r.method === 'POST' && r.path.endsWith('/completions')));
  });

  it('no PDF zone when can_attach_pdf is false', async () => {
    optionsBody = { ...OPTIONS, can_attach_pdf: false };
    await open();
    expect(document.querySelector('input[type="file"]')).toBeNull();
  });
});

describe('failures', () => {
  it('409 keeps the input, reloads the options once, and the next press carries the new revision', async () => {
    let first = true;
    onPost = () => {
      if (first) {
        first = false;
        optionsBody = { ...OPTIONS, revision: 6 };
        return json(409, { code: 'stale_revision', message: 'x' });
      }
      return json(201, RECORDED);
    };
    await ready();
    fireEvent.click(button()!);
    await until(() => expect(text()).toContain('This project changed while you were confirming.'));
    await until(() => expect(optionReads()).toHaveLength(2));
    expect((screen.getByLabelText('Completion evidence · version 2') as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText('I confirm this milestone is complete as the SOW describes it.') as HTMLInputElement).checked).toBe(true);
    expect(posts()).toHaveLength(1);
    fireEvent.click(button()!);
    await until(() => expect(posts()).toHaveLength(2));
    expect(JSON.parse(posts()[1].body).revision).toBe(6);
  });

  it('a 503 is uncertain: no resend even after 60 s; Check again reads options only', async () => {
    onPost = () => json(503, { code: 'server_error', message: 'x' });
    await ready();
    fireEvent.click(button()!);
    await until(() => expect(text()).toContain('We couldn’t tell whether this was recorded.'));
    await new Promise((r) => setTimeout(r, 20));
    expect(posts()).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Check again' }));
    await until(() => expect(text()).toContain('It wasn’t recorded.'));
    expect(posts()).toHaveLength(1);
    expect(button()).not.toBeNull();
  });

  it('uncertain then name_in_use says it is now recorded, not "Milestone recorded"', async () => {
    onPost = () => {
      optionsBody = { ...OPTIONS, can_complete: false, hold: 'name_in_use' };
      return json(503, { code: 'server_error', message: 'x' });
    };
    await ready();
    fireEvent.click(button()!);
    await until(() => expect(text()).toContain('We couldn’t tell'));
    fireEvent.click(screen.getByRole('button', { name: 'Check again' }));
    await until(() => expect(text()).toContain('A completion with this name is now recorded.'));
    expect(text()).not.toContain('Milestone recorded');
  });

  it.each([
    [403, { code: 'forbidden', message: 'x' }, 'You can’t mark this milestone complete.'],
    [404, { code: 'not_found', message: 'x' }, 'This project or milestone isn’t available to you.'],
    [422, { code: 'invalid', message: 'Check', fields: [{ name: 'name', message: 'Name is not a milestone.' }] }, 'Name is not a milestone.'],
    [400, { code: 'bad_request', message: 'x' }, 'We couldn’t record this. Check the proof and try again.'],
    [413, { code: 'too_large', message: 'x' }, 'That file is too large to upload.'],
    [415, { code: 'unsupported', message: 'x' }, 'Only a PDF can be attached as proof.'],
    [429, { code: 'rate_limited', message: 'x' }, 'Too many requests. Try again shortly.'],
  ])('a %i shows its words', async (status, body, words) => {
    onPost = () => json(status, body);
    await ready();
    fireEvent.click(button()!);
    await until(() => expect(text()).toContain(words));
    expect(text()).not.toContain('Milestone recorded');
  });

  it('options 403 and an invalid body show no control and no partial data', async () => {
    optionsBody = () => json(403, { code: 'forbidden', message: 'x' });
    await open();
    await until(() => expect(text()).toContain('This project or milestone isn’t available to you.'));
    expect(button()).toBeNull();
    cleanup();
    const { can_attach_pdf: _drop, ...bad } = OPTIONS;
    optionsBody = bad;
    await open();
    await until(() => expect(text()).toContain('We couldn’t load this milestone.'));
    expect(button()).toBeNull();
  });
});

describe('proofs', () => {
  it('Show more asks for page 2 with the name and does not duplicate ids', async () => {
    optionsBody = () => json(200, OPTIONS);
    optionsBody = { ...OPTIONS, next_page: 2 };
    await open();
    const page2 = { ...OPTIONS, proofs: [OPTIONS.proofs[1], { id: 27, label: 'Completion evidence · version 0' }], next_page: null };
    optionsBody = page2;
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await until(() => expect(screen.getByLabelText('Completion evidence · version 0')).toBeTruthy());
    expect(optionReads().at(-1)!.search).toBe(`?name=${encodeURIComponent(NAME)}&page=2`);
    expect(screen.getAllByLabelText('Completion evidence · version 1')).toHaveLength(1);
  });
});
