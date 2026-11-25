// @vitest-environment jsdom
// F-137: "Record an issue" on the live Registers tab. The fetch stand-in is the mock itself (mock/issue-record.mjs), so the 409,
// 422, 403 and uncertain answers are its own shapes. "Recorded" is asserted only after the register is read again.
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { RecordIssueDrawer } from '@/features/projects/RecordIssueDrawer';
import { bodyOf, EMPTY_DRAFT, isIssuesRead, LIMITS, problemsOf } from '@/features/projects/recordIssue';

// @ts-expect-error plain ESM module without type declarations
import { issueRecord, resetIssueRecord } from '../mock/issue-record.mjs';

vi.mock('next/navigation', () => ({ usePathname: () => '/projects/P-0101/registers', useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const CASE = 'P-0101';
const TOKEN = 'tok';
let scenario: string;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
let dropNext: boolean;
const requests = () => fetchStub.mock.calls.map(([r]) => r);
const posts = () => requests().filter((r) => r.method === 'POST');
const reloadList = vi.fn(async () => undefined);

beforeEach(() => {
  resetIssueRecord();
  scenario = 'ok';
  dropNext = false;
  reloadList.mockClear();
  setCsrfToken(TOKEN);
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: TOKEN, signed_in: true, next_url: '/' });
    if (dropNext && request.method === 'POST') {
      dropNext = false;
      throw new TypeError('network');
    }
    const raw = request.method === 'GET' ? '' : await request.clone().text();
    const r = issueRecord({ method: request.method.toLowerCase(), url, raw, persona: 'pm', cookies: { psl_mock_record: scenario }, canSee: () => true });
    return json(r.status, r.body);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

const open = async () => {
  render(<RecordIssueDrawer caseId={CASE} reloadList={reloadList} onClose={vi.fn()} pathname="/projects/P-0101/registers" />);
  await screen.findByRole('button', { name: 'Record issue' });
};
async function choose(name: string, option: string) {
  fireEvent.click(await screen.findByRole('combobox', { name: new RegExp(name) }));
  fireEvent.click(await screen.findByRole('option', { name: option }));
}
async function fill(reference = 'ISS-0301') {
  fireEvent.change(screen.getByLabelText('Reference'), { target: { value: reference } });
  fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Search is slow' } });
  fireEvent.change(screen.getByLabelText('Kind'), { target: { value: 'defect' } });
  await choose('Responsible owner', 'Kemi Adebayo');
  fireEvent.change(screen.getByLabelText('Next action'), { target: { value: 'Profile the query' } });
  await choose('Evidence', 'test report · version 2 · no. 7902');
  fireEvent.change(screen.getByLabelText('Note'), { target: { value: 'Seen on the patient list.' } });
}
const press = () => fireEvent.click(screen.getByRole('button', { name: /^(Record issue|Check the register)$/ }));

describe('the form model', () => {
  it('names every missing field and every over-long one, and sends only chosen served ids', () => {
    expect(Object.keys(problemsOf(EMPTY_DRAFT))).toEqual(['reference', 'title', 'kind', 'next_action', 'note', 'owner', 'evidence']);
    expect(problemsOf({ ...EMPTY_DRAFT, title: 'x'.repeat(LIMITS.title + 1) }).title).toMatch(/240/);
    expect(problemsOf({ ...EMPTY_DRAFT, reference: '   ' }).reference).toMatch(/Add a reference/);
    const body = bodyOf({ reference: ' R ', title: 'T', kind: 'k', owner: '5', next_action: 'n', evidence: '7902', note: 'x', severity: undefined }, 9);
    expect(body).toEqual({ case_revision: 9, reference: 'R', title: 'T', kind: 'k', owner_id: 5, next_action: 'n', evidence_id: 7902, note: 'x', severity: null, external_links: [] });
    expect(bodyOf({ ...EMPTY_DRAFT, owner: '5', evidence: '1', severity: 'Urgent' }, 1).severity).toBeNull();
    expect(bodyOf({ ...EMPTY_DRAFT, owner: '5', evidence: '1', severity: 'High' }, 1).severity).toBe('High');
  });
  it('refuses a read that is not the issues read', () => {
    expect(isIssuesRead({ case_revision: 1, issues: [], next_before: null, owners: [], proofs: [] })).toBe(true);
    expect(isIssuesRead({ case_revision: 1, issues: [], owners: [] })).toBe(false);
    expect(isIssuesRead({ case_revision: 1, issues: [], owners: [{ id: 0, name: 'x' }], proofs: [] })).toBe(false);
  });
});

describe('the drawer', () => {
  it('lists the served owners and evidence, nothing chosen, and sends nothing while a field is missing', async () => {
    await open();
    fireEvent.click(await screen.findByRole('combobox', { name: /Responsible owner/ }));
    expect((await screen.findAllByRole('option')).map((o) => o.textContent)).toEqual(['Tunde Bello', 'Kemi Adebayo', 'Engineering']);
    fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Escape' });
    press();
    expect((await screen.findAllByText(/to continue\./)).length).toBeGreaterThan(2);
    expect(posts()).toHaveLength(0);
  });

  it('sends one POST with the contract body and says recorded only after the register is read again', async () => {
    await open();
    await fill();
    await choose('Severity', 'High');
    press();
    await screen.findByText(/Recorded: ISS-0301/);
    expect(posts()).toHaveLength(1);
    expect(JSON.parse(await posts()[0].clone().text())).toEqual({
      case_revision: 7, reference: 'ISS-0301', title: 'Search is slow', kind: 'defect', owner_id: 5, next_action: 'Profile the query', evidence_id: 7902, note: 'Seen on the patient list.', severity: 'High', external_links: [],
    });
    const order = requests().map((r) => r.method);
    expect(order).toEqual(['GET', 'POST', 'GET']);
    expect(screen.getByText(/It is now Open, severity High, with Kemi Adebayo\. Next action: Profile the query/)).toBeTruthy();
    expect(reloadList).toHaveBeenCalledTimes(1);
  });

  it('does not say recorded when the re-read fails; it asks to check and sends no second POST', async () => {
    scenario = 'reread-fail';
    await open();
    await fill();
    press();
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    expect(screen.queryByText(/Recorded:/)).toBeNull();
    expect((screen.getByLabelText('Title') as HTMLInputElement).readOnly).toBe(true);
    press();
    await screen.findByText(/Recorded: ISS-0301/);
    expect(posts()).toHaveLength(1);
  });

  it('locks on a dropped connection and the check finds the issue when it was saved', async () => {
    scenario = 'uncertain-saved';
    await open();
    await fill();
    press();
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    press();
    await screen.findByText(/Recorded: ISS-0301/);
    expect(posts()).toHaveLength(1);
  });

  it('after an unsaved drop the check says it is not in the register and unlocks', async () => {
    dropNext = true;
    await open();
    await fill();
    press();
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    press();
    await screen.findByText(/isn’t in the register yet/);
    expect(screen.queryByText(/Recorded:/)).toBeNull();
    expect((screen.getByLabelText('Title') as HTMLInputElement).readOnly).toBe(false);
    expect(posts()).toHaveLength(1);
  });

  it('shows the server’s field words for a 422 and keeps the entries', async () => {
    scenario = 'invalid';
    await open();
    await fill();
    press();
    await screen.findAllByText('This reference is already used on this project.');
    expect((screen.getByLabelText('Title') as HTMLInputElement).value).toBe('Search is slow');
    expect(screen.queryByText(/Recorded:/)).toBeNull();
  });

  it('on a 409 shows the server’s words, reads the choices again and keeps the entries', async () => {
    scenario = 'conflict';
    await open();
    await fill();
    press();
    await screen.findByText(/This project changed\. Reload and try again\./);
    expect((screen.getByLabelText('Reference') as HTMLInputElement).value).toBe('ISS-0301');
    expect(requests().map((r) => r.method)).toEqual(['GET', 'POST', 'GET']);
    press();
    await screen.findByText(/Recorded: ISS-0301/);
    expect(posts()).toHaveLength(2);
  });

  it('speaks the server’s 403 on the read and offers no form', async () => {
    scenario = 'forbidden';
    render(<RecordIssueDrawer caseId={CASE} reloadList={reloadList} onClose={vi.fn()} pathname="/x" />);
    await screen.findByText('Your role does not allow recording issues here.');
    expect(screen.queryByRole('button', { name: 'Record issue' })).toBeNull();
  });

  it('offers no form when no evidence is served', async () => {
    scenario = 'empty-proofs';
    render(<RecordIssueDrawer caseId={CASE} reloadList={reloadList} onClose={vi.fn()} pathname="/x" />);
    await waitFor(() => expect(screen.getByText(/No evidence is recorded for this project/)).toBeTruthy());
    expect(screen.queryByRole('button', { name: 'Record issue' })).toBeNull();
  });
});
