// @vitest-environment jsdom
// F-11 Setup rules: list, counts, Not set, editor gating, the Set a rule save flow, proof upload, finance, delivery,
// paging, read errors and reserved tabs. fetch is stubbed; fixtures are the mock's board fixtures.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { RulesPage, RuleRow } from '@/features/setup/contract-proposal';
import { DeliveryPageView } from '@/features/setup/DeliveryRulesView';
import { FinancePageView } from '@/features/setup/FinanceRulesView';
import { fieldsFromMessage, formatSize, groupButtonLabel, isEditable, versionText } from '@/features/setup/format';
import { ReservedTab } from '@/features/setup/ReservedTab';
import { RulesPageView } from '@/features/setup/RulesView';
import { EDITOR_GONE, NOT_SAVED } from '@/features/setup/SetRulePanel';
import { AppShell } from '@/shell/AppShell';

const pathname = { value: '/setup/rules' };
vi.mock('next/navigation', () => ({
  usePathname: () => pathname.value,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const mockDir = join(__dirname, '../mock');
const read = <T,>(path: string): T => JSON.parse(readFileSync(join(mockDir, path), 'utf8')) as T;
const fixture = (name: string): RulesPage => read(`fixtures/setup/${name}.json`);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const STALE = { code: 'stale_revision', message: 'Someone changed this since you opened it. Reload to see the latest version.' };
const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow this.' };

// Every save body the UI builds is checked against the overlay and, as its v4 core, against v4 (PMO-0-2).
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const overlaySave = ajv.compile(read<{ save_body: object }>('proposals/setup.json').save_body);
const v4Doc = JSON.parse(readFileSync(join(__dirname, '../../architecture/packages/v4/openapi.json'), 'utf8')) as {
  paths: Record<string, { put: { requestBody: { content: { 'application/json': { schema: object } } } } }>;
};
const v4Save = ajv.compile(v4Doc.paths['/api/v1/setup/rules/{component}'].put.requestBody.content['application/json'].schema);

type Call = { method: string; path: string; query: string; body: unknown; csrf: string | null };
type Answer = (n: number, call: Call) => Response | Promise<Response>;
let calls: Call[];
let answers: { me: string; rules: Answer; save: Answer; upload: Answer };

const reads = () => calls.filter((c) => c.method === 'GET' && c.path === '/api/v1/setup/rules');
const saves = () => calls.filter((c) => c.method === 'PUT');
const uploads = () => calls.filter((c) => c.method === 'POST' && c.path.endsWith('/evidence'));

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-11-14T09:00:00+01:00') });
  pathname.value = '/setup/rules';
  calls = [];
  answers = {
    me: 'admin',
    rules: () => json(200, fixture('rules.desktop')),
    save: (_, c) => json(200, { component: decodeURIComponent(c.path.split('/')[5]), revision: (c.body as { expected_revision: number }).expected_revision + 1 }),
    upload: (n) => json(200, { evidence_id: `EV-${n + 1}`, sha256: 'a'.repeat(64), case_revision: n + 2 }),
  };
  const n = { rules: 0, save: 0, upload: 0 };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      const text = request.method === 'GET' ? '' : await request.clone().text();
      const c: Call = { method: request.method, path: url.pathname, query: url.search, body: text ? JSON.parse(text) : undefined, csrf: request.headers.get('X-CSRFToken') };
      calls.push(c);
      if (url.pathname === '/api/v1/me') return json(200, read(`fixtures/me.${answers.me}.json`));
      if (request.method === 'PUT') {
        expect(overlaySave(c.body), JSON.stringify(c.body)).toBe(true);
        const core = c.body as { expected_revision: number; value: unknown };
        expect(v4Save({ expected_revision: Math.max(1, core.expected_revision), value: core.value })).toBe(true);
        return answers.save(n.save++, c);
      }
      if (url.pathname.endsWith('/evidence')) return answers.upload(n.upload++, c);
      return answers.rules(n.rules++, c);
    }),
  );
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function open(view: React.ReactNode = <RulesPageView />) {
  render(<AppShell>{view}</AppShell>);
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
}
const desktop = () => within(document.querySelector('.setup-desktop') as HTMLElement);
const phone = () => within(document.querySelector('.setup-phone') as HTMLElement);
const phoneBar = () => document.querySelector('header.psl-phonebar') as HTMLElement;
const panel = () => within(screen.getByRole('region', { name: 'Set a rule' }));
const saveButton = () => panel().getByRole('button', { name: /Save as version|Saving…/ }) as HTMLButtonElement;
const rowCells = (name: string) =>
  Array.from((within(desktop().getByRole('table')).getByText(name).closest('tr') as HTMLTableRowElement).cells).map((cell) => cell.textContent);
const withPage = (page: RulesPage, change: (rows: RuleRow[]) => RuleRow[], extra: Partial<RulesPage> = {}): RulesPage => ({
  ...page,
  ...extra,
  items: change(structuredClone(page.items)),
});
const savedRow = (page: RulesPage, component: string, patch: Partial<RuleRow>) =>
  withPage(page, (rows) => rows.map((r) => (r.component === component ? { ...r, ...patch } : r)));

describe('rules list (AC 2, 3, 4)', () => {
  it('shows the board rows in order with values, versions, tags and links, and the banner from not_set_count', async () => {
    await open();
    const page = fixture('rules.desktop');
    const names = desktop()
      .getAllByRole('row')
      .slice(1)
      .map((tr) => tr.querySelector('td')?.textContent);
    expect(names).toEqual(page.items.map((r) => r.name));
    expect(rowCells('Who reviews client documents')).toEqual(['Who reviews client documents', 'All lines', 'PMO Lead', 'v2 · since 01 Oct']);
    expect(rowCells('Who may assign an RFP to a PM')).toEqual(['Who may assign an RFP to a PM', 'Pre-sale', 'Not set', 'HOLDS WORK']);
    expect(rowCells('Invoice payment terms default')).toEqual(['Invoice payment terms default', 'Finance', 'From each signed SOW', 'v1 · since 30 Jun']);
    expect(desktop().getAllByText('Not set')[0].className).toBe('setup-notset');
    expect(desktop().getByRole('link', { name: 'PSL standard pricing v4' }).getAttribute('href')).toBe('/setup/costing-rule');
    expect(desktop().getAllByRole('link', { name: 'Finance' })[0].getAttribute('href')).toBe('/setup/rules/finance');
    expect(desktop().getAllByRole('link', { name: 'Delivery' })[0].getAttribute('href')).toBe('/setup/rules/delivery');
    expect(desktop().getByText(/^8 rules aren’t set yet\. Work that needs them waits as “Setup needed”/)).toBeTruthy();
    expect(screen.getByRole('heading', { level: 1, name: 'Roles, rules and delegation' })).toBeTruthy();
    expect(phone().getByRole('heading', { level: 1 }).textContent).toBe('Rules · 8 not set');
    const back = await within(phoneBar()).findByRole('link', { name: 'Back to Setup' });
    expect(back.textContent).toBe('← Setup');
    expect(back.getAttribute('href')).toBe('/setup/roles');
    expect(phoneBar().querySelector('.shell-phonenote')).toBeNull();
    expect(phone().queryByRole('link', { name: /Setup/ })).toBeNull();
    expect(document.body.textContent).not.toContain('SAMPLE DATA');
  });

  it('frame: seven tabs in order, Rules current, badges from the count fields', async () => {
    await open();
    const tabs = within(screen.getByRole('navigation', { name: 'Setup' })).getAllByRole('link');
    expect(tabs.map((t) => [t.textContent, t.getAttribute('href')])).toEqual([
      ['Roles2', '/setup/roles'],
      ['Rules8', '/setup/rules'],
      ['Costing rule', '/setup/costing-rule'],
      ['Delegation', '/setup/delegation'],
      ['Payroll visibility', '/setup/payroll-visibility'],
      ['Staff accounts', '/setup/staff'],
      ['Templates', '/setup/templates'],
    ]);
    expect(tabs.filter((t) => t.getAttribute('aria-current') === 'page').map((t) => t.textContent)).toEqual(['Rules8']);
  });

  it('without the count fields: no badges, no banner, phone h1 "Rules"; rows never make a count', async () => {
    const page = fixture('rules.desktop');
    delete page.not_set_count;
    delete page.roles_missing_count;
    answers.rules = () => json(200, page);
    await open();
    expect(document.querySelectorAll('.psl-badge')).toHaveLength(0);
    expect(document.body.textContent).not.toMatch(/aren’t set yet|isn’t set yet/);
    expect(phone().getByRole('heading', { level: 1 }).textContent).toBe('Rules');
  });

  it('with not_set_count 0 the badge reads 0 and there is no banner; 1 reads "1 rule isn’t set yet"', async () => {
    answers.rules = () => json(200, { ...fixture('rules.desktop'), not_set_count: 0 });
    await open();
    expect(within(screen.getByRole('navigation', { name: 'Setup' })).getByRole('link', { name: /^Rules/ }).textContent).toBe('Rules0');
    expect(document.body.textContent).not.toContain('set yet');
  });

  it('a single not-set rule uses the singular banner', async () => {
    answers.rules = () => json(200, { ...fixture('rules.desktop'), not_set_count: 1 });
    await open();
    expect(desktop().getByText(/^1 rule isn’t set yet\. Work that needs it waits/)).toBeTruthy();
  });

  it('never shows an unknown as a value: set:false wins over stray values; set:true without text reads "Set"', async () => {
    answers.rules = () =>
      json(
        200,
        withPage(fixture('rules.desktop'), (rows) => [
          { ...rows[0], value: { roles: ['ceo'] }, display_value: 'CEO' },
          { ...rows[1], display_value: undefined, value: { roles: ['secret_value'] } },
          { ...rows[2], set: false, display_value: 'Old pricing' },
        ]),
      );
    await open();
    expect(rowCells('Who may assign an RFP to a PM')[2]).toBe('Not set');
    expect(rowCells('Who reviews client documents')[2]).toBe('Set');
    expect(rowCells('Costing rule')[2]).toBe('Not set');
    expect(document.body.textContent).not.toMatch(/secret_value|Old pricing/);
    expect(rowCells('Who may assign an RFP to a PM').join(' ')).not.toContain('CEO');
    expect(phone().getAllByText(/^Not set/)).toHaveLength(2);
  });

  it('version text: Lagos date, year outside the current year, bare version without a date', () => {
    const row = { component: 'c', name: 'n', set: true, revision: 3 } as RuleRow;
    const now = new Date('2026-11-14T09:00:00+01:00');
    expect(versionText({ ...row, effective_from: '2026-09-30T23:30:00Z' }, now)).toBe('v3 · since 01 Oct');
    expect(versionText({ ...row, effective_from: '2025-06-30T00:00:00+01:00' }, now)).toBe('v3 · since 30 Jun 2025');
    expect(versionText(row, now)).toBe('v3');
    expect(versionText({ ...row, set: false }, now)).toBeNull();
  });
});

describe('editor gating (AC 5, 6, 7)', () => {
  it('read-only Lead: same rows, no panel and no form controls', async () => {
    answers.rules = () => json(200, withPage(fixture('rules.desktop'), (rows) => rows.map((r) => ({ ...r, can_change: false }))));
    await open();
    expect(desktop().getAllByRole('row')).toHaveLength(11);
    expect(screen.queryByRole('region', { name: 'Set a rule' })).toBeNull();
    expect(screen.queryAllByRole('button', { name: /Save as version/ })).toHaveLength(0);
    expect(document.querySelectorAll('input, select, textarea')).toHaveLength(0);
  });

  it('only can_change + role_set + options + no link reach the picker; the panel is absent when none qualify', async () => {
    const base = fixture('rules.desktop').items[0];
    expect(isEditable(base)).toBe(true);
    expect(isEditable({ ...base, editor: { kind: 'read_only' } })).toBe(false);
    expect(isEditable({ ...base, link: 'costing-rule' })).toBe(false);
    expect(isEditable({ ...base, editor: { kind: 'role_set', options: [] } })).toBe(false);
    expect(isEditable({ ...base, can_change: undefined })).toBe(false);

    await open();
    const picker = panel().getByRole('combobox', { name: 'Rule' }) as HTMLSelectElement;
    expect(Array.from(picker.options).map((o) => o.textContent)).toEqual([
      'Who may assign an RFP to a PM',
      'Who reviews client documents',
      'Who may record an RFP outcome',
      'Who may adjust a project’s costing'.replace('’', "'"),
    ]);
  });

  it('the panel is absent when no row qualifies', async () => {
    answers.rules = () =>
      json(
        200,
        withPage(fixture('rules.desktop'), (rows) =>
          rows.map((r) => (r.can_change ? { ...r, editor: { kind: 'read_only' as const } } : { ...r, can_change: true, link: r.link })),
        ),
      );
    await open();
    expect(screen.queryByRole('region', { name: 'Set a rule' })).toBeNull();
  });

  it('/me roles have no effect: finance_lead and admin render the same list and panel', async () => {
    await open();
    const admin = document.querySelector('main')!.innerHTML;
    document.body.innerHTML = '';
    answers.me = 'finance_lead';
    await open();
    const ids = (html: string) => html.replace(/_r_\w+_|:r\w+:|«r\w+»/g, '');
    expect(ids(document.querySelector('main')!.innerHTML)).toBe(ids(admin));
  });

  it('roles allowed come from editor.options in order and start from editor.selected only', async () => {
    await open();
    const boxes = () => panel().getAllByRole('checkbox') as HTMLInputElement[];
    expect(within(panel().getByRole('group', { name: 'Roles allowed' })).getAllByRole('checkbox')).toHaveLength(3);
    expect(boxes().map((b) => [b.closest('label')!.textContent, b.checked])).toEqual([
      ['PMO Lead', false],
      ['CEO', false],
      ['PMO', false],
    ]);
    fireEvent.change(panel().getByRole('combobox', { name: 'Rule' }), { target: { value: 'documents.client_reviewer' } });
    expect(boxes().map((b) => b.checked)).toEqual([true, false, false]);
    expect(saveButton().textContent).toBe('Save as version 3');
  });
});

/** Fill the first-save edit on the RFP rule: PMO Lead, a Why and, optionally, a file. */
async function fillFirstSave({ why = 'Agreed at the PSL leadership meeting', file = true } = {}) {
  fireEvent.click(panel().getByRole('checkbox', { name: 'PMO Lead' }));
  fireEvent.change(panel().getByLabelText('Why'), { target: { value: why } });
  if (file) {
    const input = panel().getByLabelText(/^Proof/) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(['x'.repeat(2048)], 'minutes.pdf', { type: 'application/pdf' })] } });
    await waitFor(() => expect(panel().getByText('Uploaded · 2 KB')).toBeTruthy());
  }
}

describe('first save (AC 8, 9, 15)', () => {
  it('sends one PUT with exactly the edit, reloads, and announces the new version', async () => {
    let page = fixture('rules.desktop');
    answers.rules = () => json(200, page);
    answers.save = (_, c) => {
      page = savedRow({ ...page, not_set_count: 7 }, 'presale.rfp_assigner', {
        set: true,
        revision: 1,
        display_value: 'PMO Lead',
        holds_work: false,
        effective_from: '2026-11-14T00:00:00+01:00',
        editor: { ...page.items[0].editor!, selected: ['pmo_lead'] },
      });
      return json(200, { component: 'presale.rfp_assigner', revision: (c.body as { expected_revision: number }).expected_revision + 1 });
    };
    await open();
    expect(saveButton().textContent).toBe('Save as version 1');
    expect((panel().getByLabelText('Starts') as HTMLInputElement).value).toBe('2026-11-14');
    await fillFirstSave({ why: '  Agreed at the PSL leadership meeting  ' });

    expect(uploads()).toHaveLength(1);
    const up = uploads()[0];
    expect(up.path).toBe('/api/v1/cases/C-SETUP-1/evidence');
    expect(up.csrf).toBe('mock-csrf-admin');
    expect(up.body).toEqual({ kind: 'rule_proof', filename: 'minutes.pdf', content_base64: btoa('x'.repeat(2048)), case_revision: 1 });

    fireEvent.click(saveButton());
    await waitFor(() => expect(panel().getByRole('status').textContent).toBe('Saved as version 1.'));
    expect(saves()).toHaveLength(1);
    expect(saves()[0]).toMatchObject({ path: '/api/v1/setup/rules/presale.rfp_assigner', csrf: 'mock-csrf-admin' });
    expect(saves()[0].body).toEqual({ expected_revision: 0, value: { roles: ['pmo_lead'] }, starts: '2026-11-14', reason: 'Agreed at the PSL leadership meeting', evidence_id: 'EV-1' });
    expect(rowCells('Who may assign an RFP to a PM')).toEqual(['Who may assign an RFP to a PM', 'Pre-sale', 'PMO Lead', 'v1 · since 14 Nov']);
    expect(within(screen.getByRole('navigation', { name: 'Setup' })).getByRole('link', { name: /^Rules/ }).textContent).toBe('Rules7');
    expect(desktop().getByText(/^7 rules aren’t set yet/)).toBeTruthy();
    // Rebuilt from the reloaded row: next version, its selection, Why and Proof cleared; focus on the callout.
    expect(saveButton().textContent).toBe('Save as version 2');
    expect((panel().getByRole('checkbox', { name: 'PMO Lead' }) as HTMLInputElement).checked).toBe(true);
    expect((panel().getByLabelText('Why') as HTMLInputElement).value).toBe('');
    expect(panel().getByText('Choose a file')).toBeTruthy();
    // Focus moves in an effect after the outcome renders.
    await waitFor(() => expect(document.activeElement).toBe(panel().getByRole('status')));
  });

  it('a blank Why sends no reason, no upload sends no evidence_id, and a double click sends one PUT', async () => {
    let release: () => void = () => {};
    answers.save = () => new Promise<Response>((resolve) => (release = () => resolve(json(200, { component: 'presale.rfp_assigner', revision: 1 }))));
    await open();
    await fillFirstSave({ why: '   ', file: false });
    fireEvent.click(saveButton());
    fireEvent.click(saveButton());
    expect(saveButton().textContent).toBe('Saving…');
    expect(saveButton().disabled).toBe(true);
    await waitFor(() => expect(saves()).toHaveLength(1));
    await act(async () => release());
    await waitFor(() => expect(panel().getByRole('status')).toBeTruthy());
    expect(saves()).toHaveLength(1);
    expect(saves()[0].body).toEqual({ expected_revision: 0, value: { roles: ['pmo_lead'] }, starts: '2026-11-14' });
  });

  it('ticking nothing sends an empty role list and leaves the decision to the backend', async () => {
    await open();
    fireEvent.click(saveButton());
    await waitFor(() => expect(saves()).toHaveLength(1));
    expect(saves()[0].body).toEqual({ expected_revision: 0, value: { roles: [] }, starts: '2026-11-14' });
  });
});

describe('save outcomes (AC 10, 11, 13, 14)', () => {
  it('409: shows the message in a focused alert, reloads the newer version, clears every edit, never re-applies', async () => {
    let page = fixture('rules.desktop');
    answers.rules = () => json(200, page);
    answers.save = () => {
      page = savedRow(page, 'presale.rfp_assigner', { set: true, revision: 1, display_value: 'PMO Lead', holds_work: false, editor: { ...page.items[0].editor!, selected: ['pmo_lead'] } });
      return json(409, STALE);
    };
    await open();
    await fillFirstSave({ why: 'Mine' });
    fireEvent.click(panel().getByRole('checkbox', { name: 'CEO' }));
    fireEvent.click(saveButton());
    await waitFor(() => expect(panel().getByRole('alert').textContent).toBe(STALE.message));
    // Focus moves in an effect after the outcome renders.
    await waitFor(() => expect(document.activeElement).toBe(panel().getByRole('alert')));
    expect(saves()).toHaveLength(1);
    expect(reads()).toHaveLength(2);
    expect(rowCells('Who may assign an RFP to a PM')[2]).toBe('PMO Lead');
    expect((panel().getAllByRole('checkbox') as HTMLInputElement[]).map((b) => b.checked)).toEqual([true, false, false]);
    expect((panel().getByLabelText('Why') as HTMLInputElement).value).toBe('');
    expect(panel().getByText('Choose a file')).toBeTruthy();
    expect(saveButton().textContent).toBe('Save as version 2');
  });

  it('422: keeps the edits and marks the named fields', async () => {
    answers.save = () => json(422, { code: 'invalid', message: 'Check these fields: reason, starts.' });
    await open();
    await fillFirstSave({ why: 'Mine', file: false });
    fireEvent.click(saveButton());
    await waitFor(() => expect(panel().getByRole('alert').textContent).toBe('Check these fields: reason, starts.'));
    expect(panel().getByLabelText('Why').getAttribute('aria-invalid')).toBe('true');
    expect(panel().getByLabelText('Starts').getAttribute('aria-invalid')).toBe('true');
    expect(panel().getByLabelText('Why').className).toContain('is-error');
    expect(panel().getByRole('checkbox', { name: 'PMO Lead' }).getAttribute('aria-invalid')).toBeNull();
    expect((panel().getByLabelText('Why') as HTMLInputElement).value).toBe('Mine');
    expect((panel().getByRole('checkbox', { name: 'PMO Lead' }) as HTMLInputElement).checked).toBe(true);
    expect(reads()).toHaveLength(1);
  });

  it('fieldsFromMessage maps the contract names as whole words and ignores the rest', () => {
    const fields = (m: string) => [...fieldsFromMessage(m)].sort();
    expect(fields('Check these fields: value.roles.')).toEqual(['roles']);
    expect(fields('Check these fields: roles, evidence_id.')).toEqual(['evidence_id', 'roles']);
    expect(fields('Check these fields: reason, starts.')).toEqual(['reason', 'starts']);
    expect(fields('Check these fields: value.')).toEqual(['roles']);
    expect(fields('Check these fields: startsAt, reasons, colour, expected_revision.')).toEqual([]);
    expect(fields('Something went wrong.')).toEqual([]);
  });

  it('403 shows the message and reloads; the row loses its editor', async () => {
    let page = fixture('rules.desktop');
    answers.rules = () => json(200, page);
    answers.save = () => {
      page = savedRow(page, 'presale.rfp_assigner', { can_change: false });
      return json(403, FORBIDDEN);
    };
    await open();
    fireEvent.click(saveButton());
    await waitFor(() => expect(panel().getByRole('alert').textContent).toBe(FORBIDDEN.message));
    expect(reads()).toHaveLength(2);
    expect(Array.from((panel().getByRole('combobox', { name: 'Rule' }) as HTMLSelectElement).options).map((o) => o.value)).not.toContain('presale.rfp_assigner');
  });

  it('403 that leaves no editable row: the panel closes and the message stays above the list with focus (QA-1-1)', async () => {
    let page = fixture('rules.desktop');
    answers.rules = () => json(200, page);
    answers.save = () => {
      page = withPage(page, (rows) => rows.map((r) => ({ ...r, can_change: false })));
      return json(403, FORBIDDEN);
    };
    await open();
    await fillFirstSave({ why: 'Mine', file: false });
    fireEvent.click(saveButton());
    const text = `${FORBIDDEN.message} ${EDITOR_GONE} ${NOT_SAVED}`;
    await waitFor(() => expect(desktop().getByRole('alert').textContent).toBe(text));
    expect(screen.queryByRole('region', { name: 'Set a rule' })).toBeNull();
    expect(document.activeElement).toBe(desktop().getByRole('alert'));
    expect(saves()).toHaveLength(1);
    expect(reads()).toHaveLength(2);
    expect(desktop().getAllByRole('alert')).toHaveLength(1);
  });

  it('finance: a group whose only editable row loses its right keeps the 403 message above the groups with focus (QA-1-1)', async () => {
    pathname.value = '/setup/rules/finance';
    let page = fixture('finance.desktop');
    answers.rules = () => json(200, page);
    answers.save = () => {
      page = savedRow(page, 'finance.bu_totals.reviewer', { can_change: false });
      return json(403, FORBIDDEN);
    };
    await open(<FinancePageView />);
    fireEvent.click(desktop().getByRole('button', { name: 'Set BU totals rules' }));
    fireEvent.click(saveButton());
    const text = `${FORBIDDEN.message} ${EDITOR_GONE} ${NOT_SAVED}`;
    await waitFor(() => expect(desktop().getByRole('alert').textContent).toBe(text));
    expect(screen.queryByRole('region', { name: 'Set a rule' })).toBeNull();
    expect(desktop().queryByRole('button', { name: 'Set BU totals rules' })).toBeNull();
    expect(document.activeElement).toBe(desktop().getByRole('alert'));
    // Opening another group clears the old outcome.
    fireEvent.click(desktop().getByRole('button', { name: 'Set payroll rules' }));
    expect(desktop().queryByRole('alert')).toBeNull();
  });

  it('a server error whose re-read leaves every rule read-only says the panel closed but never "Nothing … saved" (SEC-2-1)', async () => {
    let page = fixture('rules.desktop');
    answers.rules = () => json(200, page);
    answers.save = () => {
      page = withPage(page, (rows) => rows.map((r) => ({ ...r, can_change: false })));
      return json(500, { code: 'server_error', message: 'Something went wrong.' });
    };
    await open();
    await fillFirstSave({ why: 'Mine', file: false });
    fireEvent.click(saveButton());
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Set a rule' })).toBeNull());
    const alert = desktop().getByRole('alert');
    expect(alert.textContent).toContain(EDITOR_GONE);
    expect(alert.textContent).not.toContain(NOT_SAVED);
    expect(saves()).toHaveLength(1);
    expect(reads()).toHaveLength(2);
  });

  it('a re-read that makes a different rule editable keeps the panel and its outcome inside it, with no page callout (TECH-2-1)', async () => {
    const others = ['documents.client_reviewer', 'presale.rfp_outcome_recorder', 'presale.costing_adjuster'];
    let page = withPage(fixture('rules.desktop'), (rows) => rows.map((r) => (others.includes(r.component) ? { ...r, can_change: false } : r)));
    answers.rules = () => json(200, page);
    answers.save = () => {
      page = withPage(page, (rows) =>
        rows.map((r) => (r.component === 'presale.rfp_assigner' ? { ...r, can_change: false } : r.component === 'documents.client_reviewer' ? { ...r, can_change: true } : r)),
      );
      return json(403, FORBIDDEN);
    };
    await open();
    fireEvent.click(saveButton());
    await waitFor(() => expect(panel().getByRole('alert').textContent).toBe(FORBIDDEN.message));
    expect(desktop().getAllByRole('alert')).toHaveLength(1);
    expect(document.body.textContent).not.toContain(EDITOR_GONE);
    expect((panel().getByRole('combobox', { name: 'Rule' }) as HTMLSelectElement).value).toBe('documents.client_reviewer');
  });

  it('rules: a Show more that brings the panel back drops the stale "panel has closed" callout (TECH-2-1)', async () => {
    const first = fixture('rules.desktop');
    let firstPage = withPage(first, (rows) => rows.map((r) => (r.component === 'presale.rfp_assigner' ? r : { ...r, can_change: false })), { next_cursor: 'o:10' });
    const more = { items: [{ ...first.items[1], component: 'later.reviewer', name: 'A later rule' }], as_of: first.as_of };
    answers.rules = (_, c) => (c.query.includes('cursor=') ? json(200, more) : json(200, firstPage));
    answers.save = () => {
      firstPage = savedRow(firstPage, 'presale.rfp_assigner', { can_change: false });
      return json(403, FORBIDDEN);
    };
    await open();
    fireEvent.click(saveButton());
    await waitFor(() => expect(desktop().getByRole('alert').textContent).toContain(EDITOR_GONE));
    expect(screen.queryByRole('region', { name: 'Set a rule' })).toBeNull();
    fireEvent.click(desktop().getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(screen.getByRole('region', { name: 'Set a rule' })).toBeTruthy());
    expect(document.body.textContent).not.toContain(EDITOR_GONE);
    expect((panel().getByRole('combobox', { name: 'Rule' }) as HTMLSelectElement).value).toBe('later.reviewer');
  });

  it('network error, revision unchanged: re-reads once, keeps the edits, never resends', async () => {
    answers.save = () => Promise.reject(new TypeError('Failed to fetch'));
    await open();
    await fillFirstSave({ why: 'Mine', file: false });
    fireEvent.click(saveButton());
    await waitFor(() =>
      expect(panel().getByRole('alert').textContent).toBe('We couldn’t confirm the save. Nothing new is shown for this rule, so you can save again.'),
    );
    expect(saves()).toHaveLength(1);
    expect(reads()).toHaveLength(2);
    expect((panel().getByLabelText('Why') as HTMLInputElement).value).toBe('Mine');
    expect(saveButton().disabled).toBe(false);
  });

  it('network error, revision changed: clears the edits with "This rule changed…"', async () => {
    let page = fixture('rules.desktop');
    answers.rules = () => json(200, page);
    answers.save = () => {
      page = savedRow(page, 'presale.rfp_assigner', { set: true, revision: 1, display_value: 'PMO Lead', holds_work: false });
      return json(503, { code: 'unavailable', message: 'Down' });
    };
    await open();
    await fillFirstSave({ why: 'Mine', file: false });
    fireEvent.click(saveButton());
    await waitFor(() => expect(panel().getByRole('alert').textContent).toBe('This rule changed. Check the version shown before saving again.'));
    expect((panel().getByLabelText('Why') as HTMLInputElement).value).toBe('');
    expect(saveButton().textContent).toBe('Save as version 2');
    expect(saves()).toHaveLength(1);
  });

  it('network error and the re-read fails: Save stays off until another rule is picked', async () => {
    answers.rules = (n) => (n === 0 ? json(200, fixture('rules.desktop')) : Promise.reject(new TypeError('Failed to fetch')));
    answers.save = () => Promise.reject(new TypeError('Failed to fetch'));
    await open();
    fireEvent.click(saveButton());
    await waitFor(() => expect(panel().getByRole('alert').textContent).toBe('We couldn’t check whether the save went through. Reload the page before saving again.'));
    expect(saveButton().disabled).toBe(true);
    fireEvent.click(saveButton());
    expect(saves()).toHaveLength(1);
    fireEvent.change(panel().getByRole('combobox', { name: 'Rule' }), { target: { value: 'documents.client_reviewer' } });
    expect(saveButton().disabled).toBe(false);
  });

  it('401 on save shows the signed-out state with next=/setup/rules', async () => {
    answers.save = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open();
    fireEvent.click(saveButton());
    await waitFor(() => expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fsetup%2Frules'));
    expect(screen.queryByRole('table')).toBeNull();
  });
});

describe('proof (AC 15)', () => {
  it('a second file in the same edit sends the returned case_revision; a row without proof_case is disabled', async () => {
    await open();
    const input = () => panel().getByLabelText(/^Proof/) as HTMLInputElement;
    fireEvent.change(input(), { target: { files: [new File(['a'], 'one.pdf')] } });
    await waitFor(() => expect(panel().getByText('one.pdf')).toBeTruthy());
    fireEvent.change(input(), { target: { files: [new File(['b'], 'two.pdf')] } });
    await waitFor(() => expect(panel().getByText('two.pdf')).toBeTruthy());
    expect(uploads().map((u) => (u.body as { case_revision: number }).case_revision)).toEqual([1, 2]);
    fireEvent.click(saveButton());
    await waitFor(() => expect(saves()).toHaveLength(1));
    expect((saves()[0].body as { evidence_id: string }).evidence_id).toBe('EV-2');

    fireEvent.change(panel().getByRole('combobox', { name: 'Rule' }), { target: { value: 'presale.rfp_outcome_recorder' } });
    const drop = panel().getByText('Proof can’t be attached here yet.');
    expect(drop.className).toBe('psl-drop is-disabled setup-drop');
    expect(drop.getAttribute('aria-disabled')).toBe('true');
    expect(panel().queryByLabelText(/^Proof/)).toBeNull();
  });

  it('a 422 upload marks Proof invalid and Save still works without evidence_id', async () => {
    answers.upload = () => json(422, { code: 'invalid', message: 'Check these fields: content_base64.' });
    await open();
    fireEvent.change(panel().getByLabelText(/^Proof/), { target: { files: [new File(['a'], 'one.exe')] } });
    await waitFor(() => expect(panel().getByText('Check these fields: content_base64.')).toBeTruthy());
    expect(panel().getByLabelText(/^Proof/).getAttribute('aria-invalid')).toBe('true');
    fireEvent.click(saveButton());
    await waitFor(() => expect(saves()).toHaveLength(1));
    expect(saves()[0].body).not.toHaveProperty('evidence_id');
  });

  it('409 asks for the file again and re-reads the list; a network failure never retries', async () => {
    answers.upload = (n) => (n === 0 ? json(409, STALE) : Promise.reject(new TypeError('Failed to fetch')));
    await open();
    fireEvent.change(panel().getByLabelText(/^Proof/), { target: { files: [new File(['a'], 'one.pdf')] } });
    await waitFor(() => expect(panel().getByText('The record changed. Choose the file again.')).toBeTruthy());
    await waitFor(() => expect(reads()).toHaveLength(2));
    fireEvent.change(panel().getByLabelText(/^Proof/), { target: { files: [new File(['a'], 'one.pdf')] } });
    await waitFor(() => expect(panel().getByText('We couldn’t attach the file. Choose it again.')).toBeTruthy());
    expect(uploads()).toHaveLength(2);
  });

  it('sizes read in KB below 1024 KB, else MB', () => {
    expect(formatSize(120 * 1024)).toBe('120 KB');
    expect(formatSize(1)).toBe('1 KB');
    expect(formatSize(1024 * 1024)).toBe('1.0 MB');
    expect(formatSize(1.55 * 1024 * 1024)).toBe('1.6 MB');
  });
});

describe('read states and paging (AC 14, 19, 21)', () => {
  it('401 on read shows the signed-out state; 403 and 404 show no-access and no rule', async () => {
    answers.rules = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open();
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fsetup%2Frules');
    for (const status of [403, 404]) {
      document.body.innerHTML = '';
      answers.rules = () => json(status, FORBIDDEN);
      await open();
      expect(screen.getByText('This section isn’t open to your role.')).toBeTruthy();
      expect(document.body.textContent).not.toMatch(/RFP|Roles, rules/);
    }
  });

  it('pm without the setup destination sees no-access and no rules call', async () => {
    answers.me = 'pm';
    await open();
    expect(screen.getByText('This section isn’t open to your role.')).toBeTruthy();
    expect(reads()).toHaveLength(0);
  });

  it('a server error shows the load error card and Try again re-reads', async () => {
    answers.rules = (n) => (n === 0 ? json(500, { code: 'server_error', message: 'Boom' }) : json(200, fixture('rules.desktop')));
    await open();
    expect(screen.getByRole('alert').textContent).toContain('We couldn’t load the rules. Your work is safe; nothing was changed.');
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(desktop().getAllByRole('row')).toHaveLength(11));
  });

  it('Show more appends the next page in order and keeps the first page counts; a failed page keeps the rows', async () => {
    const rows = Array.from({ length: 55 }, (_, i) => ({ component: `r${i}`, name: `Sample rule ${i + 1}`, set: false, revision: 0 }));
    answers.rules = (_, c) => {
      if (c.query.includes('cursor=o%3A50')) return failMore ? json(500, { code: 'x', message: 'x' }) : json(200, { items: rows.slice(50), as_of: 'x', not_set_count: 99 });
      return json(200, { items: rows.slice(0, 50), as_of: '2026-11-12T10:40:00+01:00', next_cursor: 'o:50', not_set_count: 55 });
    };
    let failMore = true;
    await open();
    expect(desktop().getAllByRole('row')).toHaveLength(51);
    fireEvent.click(desktop().getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(desktop().getByText('We couldn’t load more rules. Choose Show more to try again.')).toBeTruthy());
    expect(desktop().getAllByRole('row')).toHaveLength(51);
    failMore = false;
    fireEvent.click(desktop().getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(desktop().getAllByRole('row')).toHaveLength(56));
    expect(desktop().queryByRole('button', { name: 'Show more' })).toBeNull();
    expect(desktop().getAllByRole('row')[55].textContent).toContain('Sample rule 55');
    expect(within(screen.getByRole('navigation', { name: 'Setup' })).getByRole('link', { name: /^Rules/ }).textContent).toBe('Rules55');
  });

  it('empty keeps the frame and shows the empty pattern without banner or panel', async () => {
    answers.rules = () => json(200, { items: [], as_of: '2026-11-12T10:40:00+01:00', not_set_count: 0 });
    await open();
    expect(screen.getByRole('navigation', { name: 'Setup' })).toBeTruthy();
    expect(desktop().getByRole('heading', { level: 2, name: 'No rules to show.' })).toBeTruthy();
    expect(screen.queryByRole('region', { name: 'Set a rule' })).toBeNull();
    expect(document.body.textContent).not.toContain('set yet');
  });
});

describe('finance and delivery views (AC 16, 17)', () => {
  it('finance: crumb, lead, the count callout and seven groups with their Set … rules disclosures', async () => {
    pathname.value = '/setup/rules/finance';
    answers.rules = () => json(200, fixture('finance.desktop'));
    await open(<FinancePageView />);
    expect(reads()[0].query).toBe('?area=finance');
    expect(desktop().getByRole('navigation', { name: 'Breadcrumb' }).textContent).toBe('SETUP / RULES / FINANCE');
    expect(desktop().getByRole('heading', { level: 1, name: 'Finance rules' })).toBeTruthy();
    expect(desktop().getByText('All 25 values are Not set. Real reviewers and approvers come from PSL; none are invented here.')).toBeTruthy();
    const heads = desktop().getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(heads).toEqual(['Management accounts', 'Income schedules', 'Asset schedule', 'Cash forecast', 'BU totals', 'Ledger sources', 'Payroll']);
    expect(desktop().getAllByText('NOT SET')).toHaveLength(25);
    const buttons = desktop().getAllByRole('button', { name: /^Set .* rules$/ });
    expect(buttons.map((b) => b.textContent)).toEqual([
      'Set management accounts rules',
      'Set income schedules rules',
      'Set asset schedule rules',
      'Set cash forecast rules',
      'Set BU totals rules',
      'Set ledger sources rules',
      'Set payroll rules',
    ]);
    expect(screen.queryByRole('region', { name: 'Set a rule' })).toBeNull();
    fireEvent.click(buttons[6]);
    expect(buttons[6].getAttribute('aria-expanded')).toBe('true');
    expect(document.getElementById(buttons[6].getAttribute('aria-controls')!)!.hidden).toBe(false);
    expect(Array.from((panel().getByRole('combobox', { name: 'Rule' }) as HTMLSelectElement).options).map((o) => o.textContent)).toEqual([
      'Who may read inputs',
      'Who reviews payroll',
    ]);
    fireEvent.click(buttons[0]);
    expect(buttons[6].getAttribute('aria-expanded')).toBe('false');
    expect(screen.getAllByRole('region', { name: 'Set a rule' })).toHaveLength(1);
    fireEvent.click(buttons[0]);
    expect(screen.queryByRole('region', { name: 'Set a rule' })).toBeNull();

    expect(phone().getByText('25 values Not set.')).toBeTruthy();
    expect(phone().getByText('+ 4 MORE LINES · OPEN ON DESKTOP')).toBeTruthy();
    expect(within(phoneBar()).getByRole('link', { name: 'Back to Setup' }).getAttribute('href')).toBe('/setup/roles');
    expect(phoneBar().querySelector('.shell-phonenote')?.textContent).toBe('RULES');
  });

  it('finance read-only: no Set buttons; rows without group go last; count absent leaves one sentence', async () => {
    pathname.value = '/setup/rules/finance';
    const page = withPage(fixture('finance.desktop'), (rows) => [
      ...rows.map((r) => ({ ...r, can_change: false })),
      { component: 'finance.loose', name: 'Loose rule', set: true, revision: 1, display_value: 'Monthly' },
    ]);
    delete page.not_set_count;
    answers.rules = () => json(200, page);
    await open(<FinancePageView />);
    expect(screen.queryAllByRole('button', { name: /^Set / })).toHaveLength(0);
    expect(desktop().getAllByRole('heading', { level: 2 }).at(-1)!.textContent).toBe('Other Finance rules');
    expect(desktop().getByText('Monthly')).toBeTruthy();
    expect(desktop().getByText('Real reviewers and approvers come from PSL; none are invented here.')).toBeTruthy();
    expect(groupButtonLabel('BU totals')).toBe('Set BU totals rules');
  });

  it('delivery: table with RULE, VALUE, USED BY, the set row, the info callout, Next and no controls', async () => {
    pathname.value = '/setup/rules/delivery';
    answers.rules = () => json(200, fixture('delivery.desktop'));
    await open(<DeliveryPageView />);
    expect(reads()[0].query).toBe('?area=delivery');
    expect(desktop().getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['RULE', 'VALUE', 'USED BY']);
    expect(desktop().getAllByRole('row')).toHaveLength(6);
    expect(rowCells('Archive storage rule')).toEqual(['Archive storage rule', 'Keep, never purge', 'Archive']);
    expect(rowCells('Hypercare window')).toEqual(['Hypercare window', 'NOT SET', 'Hypercare']);
    expect(desktop().getByText(/^These are PSL’s decisions\. Until a rule is set/)).toBeTruthy();
    expect(desktop().getByText('Each rule is versioned. Changing one doesn’t change work already finished.')).toBeTruthy();
    expect(document.querySelectorAll('input, select, textarea, button:not(.shell-menubutton)')).toHaveLength(0);
  });
});

describe('reserved tabs (AC 20)', () => {
  it('shows the frame with that tab current, no badges, the empty pattern and makes no setup call', async () => {
    pathname.value = '/setup/delegation';
    await open(<ReservedTab tab="delegation" />);
    const nav = screen.getByRole('navigation', { name: 'Setup' });
    expect(within(nav).getByRole('link', { name: 'Delegation' }).getAttribute('aria-current')).toBe('page');
    expect(nav.querySelectorAll('.psl-badge')).toHaveLength(0);
    expect(screen.getByRole('heading', { level: 2, name: 'Delegation comes next.' })).toBeTruthy();
    expect(calls.map((c) => c.path)).toEqual(['/api/v1/me']);
  });

  it('pm gets no-access', async () => {
    answers.me = 'pm';
    await open(<ReservedTab tab="templates" />);
    expect(screen.getByText('This section isn’t open to your role.')).toBeTruthy();
  });
});
