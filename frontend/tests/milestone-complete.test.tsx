// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MilestoneCompletePage } from '@/features/projects/MilestoneComplete';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { projects } from '../mock/projects.mjs';
import { bellFeed, isBellFeed, isRoleDashboard, roleDashboard } from './bell-feed';

vi.mock('next/navigation', () => ({ usePathname: () => '/projects/P-0101/milestones/complete', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }), useSearchParams: () => new URLSearchParams() }));

const me = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/me.pm.json'), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const CASE = '00000000-0000-4000-8000-000000000101';
const NAME = 'UAT sign-off';
const OPTIONS = { revision: 5, proofs: [{ id: 31, label: 'Completion evidence · version 2' }, { id: 29, label: 'Completion evidence · version 1' }], next_page: null, can_complete: true, can_attach_pdf: true, hold: null };
const RECORDED = { id: 412, revision: 6, name: NAME, evidence_id: 31 };
const REREAD = { id: 412, name: NAME, completed_at: '2026-11-23T10:15:00Z', evidence_id: 31, proof_version: 3 };

type Req = { method: string; path: string; search: string; body: string; csrf: string | null };
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
      log.push({ method: input.method, path: url.pathname.replace(CASE, 'CASE'), search: url.search, body, csrf: input.headers.get('X-CSRFToken') });
      if (url.pathname === `/api/v1/projects/${CASE}`) {
        const r = projects({ operationId: 'E-PROJECT', url: new URL('http://x/api/v1/projects/P-0101'), persona: 'pm' });
        return json(r.status, r.body);
      }
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
  await until(() => expect(text()).not.toContain('Loading…'));
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

const fileInput = () => document.querySelector('input[type="file"]') as HTMLInputElement;
const choose = (file: File) => fireEvent.change(fileInput(), { target: { files: [file] } });
async function uploadPdf(name: string) {
  choose(new File(['%PDF'], name, { type: 'application/pdf' }));
  await until(() => expect(screen.queryByLabelText('I have checked this file is the proof for this milestone.')).not.toBeNull());
}
const phone = () => vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('max-width'), media: q, addEventListener: () => {}, removeEventListener: () => {} }));

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
    const press = button()!;
    fireEvent.click(press);
    fireEvent.click(press);
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
    await uploadPdf('signoff.pdf');
    confirmBox();
    await until(() => expect(screen.queryByLabelText('I have checked this file is the proof for this milestone.')).not.toBeNull());
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
    const bad: Record<string, unknown> = { ...OPTIONS };
    delete bad.can_attach_pdf;
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

describe('round 2: layout, holds, the file, and the remaining criteria', () => {
  it.each([
    ['name_in_use', { can_complete: false, hold: 'name_in_use' }],
    ['norole', { can_complete: false, hold: null }],
    ['baseline_required', { can_complete: false, hold: 'baseline_required' }],
  ])('UI-1-4: under %s there are no proof radios and no upload zone', async (_n, patch) => {
    optionsBody = { ...OPTIONS, ...patch };
    await open();
    expect(document.querySelector('input[type="radio"]')).toBeNull();
    expect(fileInput()).toBeNull();
    expect(text()).not.toContain('Evidence');
  });

  it('proof_required keeps only the PDF zone when can_attach_pdf is true', async () => {
    optionsBody = { ...OPTIONS, can_complete: false, hold: 'proof_required', proofs: [] };
    await open();
    expect(document.querySelector('input[type="radio"]')).toBeNull();
    expect(fileInput()).not.toBeNull();
    expect(button()).toBeNull();
  });

  it('desktop shows the read-only Project and Milestone fields; the card has the dark head', async () => {
    await open();
    await until(() => expect(document.querySelectorAll('.mscomplete__box')).toHaveLength(2));
    expect([...document.querySelectorAll('.mscomplete__box')].map((b) => b.textContent)).toEqual(['Lagoon Health · patient app', NAME]);
    expect(document.querySelector('.psl-panel__head--dark')!.textContent).toBe('Milestone');
  });

  it('UI-1-3: phone is flat, the milestone name is the heading, there is no breadcrumb', async () => {
    phone();
    await open();
    expect(screen.getByRole('heading', { level: 1, name: NAME })).toBeTruthy();
    expect(document.querySelector('.psl-crumb')).toBeNull();
    expect(document.querySelector('.mscomplete__card')).toBeNull();
    expect(button()).not.toBeNull();
  });

  it('TECH-1-1: a PNG is refused before any request; the input is named "Or upload a private PDF"', async () => {
    await open();
    expect(fileInput().getAttribute('accept')).toBe('.pdf');
    expect(screen.getByLabelText('Or upload a private PDF', { selector: 'input' })).toBe(fileInput());
    choose(new File(['x'], 'photo.png', { type: 'image/png' }));
    await until(() => expect(text()).toContain('PNG files can’t be used as proof'));
    expect(log.some((r) => r.path.endsWith('/files'))).toBe(false);
  });

  it.each([
    [413, 'too_large', 'That file is too large to upload.'],
    [415, 'unsupported', 'Only a PDF can be attached as proof.'],
  ])('TECH-1-1: an upload %i says the spec wording', async (status, code, words) => {
    onFile = () => json(status, { code, message: 'x' });
    await open();
    choose(new File(['%PDF'], 'a.pdf', { type: 'application/pdf' }));
    await until(() => expect(text()).toContain(words));
  });

  it('TECH-1-2: the file tick is cleared when the file is removed and another is uploaded', async () => {
    await open();
    await uploadPdf('a.pdf');
    confirmBox();
    fireEvent.click(screen.getByLabelText('I have checked this file is the proof for this milestone.'));
    expect(button()!.disabled).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /Remove/ }));
    await until(() => expect(screen.queryByLabelText('I have checked this file is the proof for this milestone.')).toBeNull());
    await uploadPdf('b.pdf');
    expect((screen.getByLabelText('I have checked this file is the proof for this milestone.') as HTMLInputElement).checked).toBe(false);
    expect(button()!.disabled).toBe(true);
    expect(posts()).toHaveLength(0);
  });

  it('AC 9: a 409 keeps the uploaded PDF and both ticks', async () => {
    let first = true;
    onPost = () => {
      if (first) {
        first = false;
        return json(409, { code: 'stale_revision', message: 'x' });
      }
      return json(201, RECORDED);
    };
    await open();
    await uploadPdf('a.pdf');
    confirmBox();
    fireEvent.click(screen.getByLabelText('I have checked this file is the proof for this milestone.'));
    fireEvent.click(button()!);
    await until(() => expect(text()).toContain('This project changed while you were confirming.'));
    expect(text()).toContain('signoff.pdf');
    expect((screen.getByLabelText('I have checked this file is the proof for this milestone.') as HTMLInputElement).checked).toBe(true);
    expect(button()!.disabled).toBe(false);
  });

  it('AC 9: a 409 that drops the chosen proof deselects it with a note', async () => {
    onPost = () => {
      optionsBody = { ...OPTIONS, revision: 6, proofs: [OPTIONS.proofs[1]] };
      return json(409, { code: 'stale_revision', message: 'x' });
    };
    await ready();
    fireEvent.click(button()!);
    await until(() => expect(text()).toContain('That proof is no longer available.'));
    expect((screen.getByLabelText('Completion evidence · version 1') as HTMLInputElement).checked).toBe(false);
  });

  it('TECH-1-4: a 409 whose reload fails says so, and the form stays busy until the reload settles', async () => {
    onPost = () => {
      optionsBody = () => json(500, { code: 'server_error', message: 'x' });
      return json(409, { code: 'stale_revision', message: 'x' });
    };
    await ready();
    fireEvent.click(button()!);
    await until(() => expect(text()).toContain('we couldn’t reload it'));
    expect(text()).not.toContain('We reloaded it.');
  });

  it('AC 10: "It wasn’t recorded" keeps the proof and the tick', async () => {
    onPost = () => json(503, { code: 'server_error', message: 'x' });
    await ready();
    fireEvent.click(button()!);
    await until(() => expect(text()).toContain('We couldn’t tell'));
    fireEvent.click(screen.getByRole('button', { name: 'Check again' }));
    await until(() => expect(text()).toContain('It wasn’t recorded.'));
    expect((screen.getByLabelText('Completion evidence · version 2') as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText('I confirm this milestone is complete as the SOW describes it.') as HTMLInputElement).checked).toBe(true);
  });

  it('AC 11: a 401 on the write shows the signed-out state', async () => {
    onPost = () => json(401, { code: 'not_authenticated', message: 'x' });
    await ready();
    fireEvent.click(button()!);
    await until(() => expect(text()).toContain('You’re signed out.'));
  });

  it('TECH-1-8: a 401 on the re-read after a 201 says the completion was saved', async () => {
    onReread = () => json(401, { code: 'not_authenticated', message: 'x' });
    await ready();
    fireEvent.click(button()!);
    await until(() => expect(text()).toContain('We saved your completion'));
    expect(text()).toContain('You’re signed out.');
    expect(text()).not.toContain('Milestone recorded');
  });

  it('TECH-1-5: a 422 without a field message shows the fallback, not the server text', async () => {
    onPost = () => json(422, { code: 'invalid', message: 'SECRET server text' });
    await ready();
    fireEvent.click(button()!);
    await until(() => expect(text()).toContain('We couldn’t record this. Check the proof and try again.'));
    expect(text()).not.toContain('SECRET');
  });

  it('AC 12: a 404 and a 500 on the options read', async () => {
    optionsBody = () => json(404, { code: 'not_found', message: 'x' });
    await open();
    expect(text()).toContain('This project or milestone isn’t available to you.');
    cleanup();
    optionsBody = () => json(500, { code: 'server_error', message: 'x' });
    await open();
    await until(() => expect(text()).toContain('We couldn’t load this milestone.'));
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy();
    expect(button()).toBeNull();
  });

  it('SEC-1-2: the write carries the X-CSRFToken from /me; AC 13: the Recorded text is the fixed wording and only allowed requests are made', async () => {
    await ready();
    fireEvent.click(button()!);
    await until(() => expect(text()).toContain('Milestone recorded'));
    expect(posts()[0].csrf).toBe('mock-csrf-pm');
    expect(text()).toContain('Finance is handed this milestone and starts any invoice itself. The amount comes from the contract, not from this form. Completing a milestone is not invoicing it. PMO completes milestones; Finance handles invoices.');
    const allowed = [/\/milestones\/completions$/, /\/milestones\/\d+$/, /\/files$/, /\/projects\/CASE$/];
    expect(log.filter((r) => !allowed.some((a) => a.test(r.path)))).toEqual([]);
  });
});
