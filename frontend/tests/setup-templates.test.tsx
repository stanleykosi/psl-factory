// @vitest-environment jsdom
// F-20 Setup templates: list, badge and copy rules, upload gating, the E-TEMPLATE-VERSION request, and every outcome
// (200, 409, 422, 401, 403/404, network), double submit, paging, empty, read-only, titles and tabs. fetch is stubbed;
// fixtures are the mock's.
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { TemplatesPage, TemplateRow } from '@/features/setup/api';
import { boardDay, boardStamp } from '@/features/setup/format';
import { TemplatesPageView } from '@/features/setup/TemplatesView';
import { SetupLayoutFrame } from '@/features/setup/SetupFrame';
import { AppShell } from '@/shell/AppShell';
import { bellFeed, isBellFeed, isRoleDashboard, roleDashboard } from './bell-feed';

const pathname = { value: '/setup/templates' };
vi.mock('next/navigation', () => ({
  usePathname: () => pathname.value,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const mockDir = join(__dirname, '../mock');
const read = <T,>(path: string): T => JSON.parse(readFileSync(join(mockDir, path), 'utf8')) as T;
const fixture = (name: string): TemplatesPage => read(`fixtures/templates/${name}.json`);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const STALE = { code: 'stale_revision', message: 'This template changed. Reload to see the newer version.' };
const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow this.' };
const BOOM = { code: 'server_error', message: 'Something broke.' };

type Call = { method: string; path: string; query: string; body: Record<string, unknown> | undefined; csrf: string | null };
type Answer = (n: number, call: Call) => Response | Promise<Response>;
let calls: Call[];
let answers: { me: string; list: Answer; upload: Answer };

const lists = () => calls.filter((c) => c.method === 'GET' && c.path === '/api/v1/setup/templates');
const uploads = () => calls.filter((c) => c.method === 'POST');

/** A list answer that follows the uploads: a 200 raises the row's version and revision as the backend would. */
function liveList(start: TemplatesPage) {
  const page = structuredClone(start);
  return {
    list: () => json(200, page),
    upload: (_: number, c: Call) => {
      const id = decodeURIComponent(c.path.split('/')[5]);
      const row = page.items.find((r) => r.template_id === id)!;
      row.version = String(Number(row.version) + 1);
      row.versions = (row.versions ?? 0) + 1;
      row.revision = (row.revision ?? 0) + 1;
      row.updated_by = 'Ada Okafor';
      row.updated_at = '2026-11-14T08:30:00+01:00';
      return json(200, { template_id: id, version: row.version, test_template: row.test_template, revision: row.revision });
    },
    page,
  };
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-11-14T09:00:00+01:00') });
  pathname.value = '/setup/templates';
  calls = [];
  answers = {
    me: 'admin',
    list: () => json(200, fixture('desktop')),
    upload: (_, c) => json(200, { template_id: decodeURIComponent(c.path.split('/')[5]), version: '2', test_template: true, revision: 2 }),
  };
  const n = { list: 0, upload: 0 };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
      if (isRoleDashboard(request)) return roleDashboard();
      const url = new URL(request.url);
      const text = request.method === 'GET' ? '' : await request.clone().text();
      const c: Call = { method: request.method, path: url.pathname, query: url.search, body: text ? JSON.parse(text) : undefined, csrf: request.headers.get('X-CSRFToken') };
      calls.push(c);
      if (url.pathname === '/api/v1/me') return json(200, read(`fixtures/me.${answers.me}.json`));
      if (request.method === 'POST') return answers.upload(n.upload++, c);
      return answers.list(n.list++, c);
    }),
  );
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function open() {
  render(
    <AppShell>
      <SetupLayoutFrame>
        <TemplatesPageView />
      </SetupLayoutFrame>
    </AppShell>,
  );
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
}
const desktop = () => within(document.querySelector('.setup-desktop') as HTMLElement);
// the frame the Setup layout draws on desktop, beside the page's own desktop body
const frame = () => within(document.querySelector('.setup-frame--desktop') as HTMLElement);
const phone = () => within(document.querySelector('.setup-phone') as HTMLElement);
const phoneBar = () => document.querySelector('header.psl-phonebar') as HTMLElement;
const rowOf = (name: string) => within(desktop().getByRole('table')).getByText(name).closest('tr') as HTMLTableRowElement;
const cardOf = (name: string) => phone().getByText(name).closest('li') as HTMLElement;
const names = () =>
  desktop()
    .getAllByRole('row')
    .slice(1)
    .map((tr) => tr.querySelector('td strong')?.textContent);
const UPLOAD = "Upload PSL's version";
const panel = () => within(desktop().getByRole('region', { name: /^Upload a version of/ }));
const announced = () => document.querySelector('.psl-toast')?.textContent; // D-151: the toast, which is announced as a status
const withRows = (page: TemplatesPage, change: (rows: TemplateRow[]) => TemplateRow[], extra: Partial<TemplatesPage> = {}): TemplatesPage => ({ ...page, ...extra, items: change(structuredClone(page.items)) });
const pdf = (name = 'invoice-v2.pdf', content: BlobPart = new Uint8Array([0x25, 0x50, 0x44, 0x46])) => new File([content], name, { type: 'application/pdf' });

async function openPanel(name: string) {
  fireEvent.click(within(rowOf(name)).getByRole('button', { name: /^Upload / }));
  return panel();
}
function choose(p: ReturnType<typeof panel>, file: File, note?: string) {
  fireEvent.change(p.getByLabelText('File'), { target: { files: [file] } });
  if (note !== undefined) fireEvent.change(p.getByLabelText('Note (optional)'), { target: { value: note } });
}
const send = () => fireEvent.click(panel().getByRole('button', { name: /^Upload version$|^Uploading…$/ }));
const submit = () => panel().getByRole('button', { name: /^Upload version$|^Uploading…$/ }) as HTMLButtonElement;

describe('the list (AC 4)', () => {
  it('shows the eight names and lines in the order returned, each with the tag, and the version lines only where returned', async () => {
    await open();
    const page = fixture('desktop');
    expect(names()).toEqual(page.items.map((r) => r.name));
    const first = rowOf('Invoice');
    expect(within(first).getByText('Invoice preparation and delivery')).toBeTruthy();
    expect(within(first).getByText('TEST TEMPLATE')).toBeTruthy();
    expect(within(first).getByText('Version 1 · PDF')).toBeTruthy();
    expect(within(first).queryByText(/Changed/)).toBeNull();
    const sow = rowOf('Closure report');
    expect(within(sow).getByText('Version 3 · PDF')).toBeTruthy();
    expect(within(sow).getByText('3 versions · Changed by Ada Okafor, 12 Nov')).toBeTruthy();
    expect(desktop().getAllByText('TEST TEMPLATE')).toHaveLength(8);
    expect(desktop().getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['DOCUMENT', 'USED BY LINE', 'STATUS', 'Action']);
  });

  it('with history on every row, the line sits under the name in the Document cell, for read-only rows too', async () => {
    const all = (rows: TemplatesPage['items']) => rows.map((r) => ({ ...r, versions: 2, updated_by: 'Ada Okafor', updated_at: '2025-06-30T10:00:00Z' }));
    answers.list = () => json(200, withRows(fixture('readonly'), all));
    await open();
    const history = desktop().getAllByText(/^2 versions · Changed by Ada Okafor, /);
    expect(history).toHaveLength(8);
    for (const line of history) {
      expect(line.closest('td')).toBe(within(line.closest('tr')!).getAllByRole('cell')[0]);
    }
    expect(desktop().queryByRole('button', { name: /Upload/ })).toBeNull();
  });

  it('the phone as-of line sits under the note, before the cards', async () => {
    await open();
    const asOf = phone().getByText('AS OF 12 NOV, 10:40');
    const note = phone().getByText('All 8 are test templates until PSL supplies its own.');
    const list = phone().getByRole('list');
    expect(note.compareDocumentPosition(asOf) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(asOf.compareDocumentPosition(list) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('follows the API order, and a name not in the fixture appears nowhere', async () => {
    const page = withRows(fixture('desktop'), (rows) => rows.reverse().map((r, i) => (i === 0 ? { ...r, name: 'Closure pack' } : r)));
    answers.list = () => json(200, page);
    await open();
    expect(names()).toEqual(page.items.map((r) => r.name));
    expect(names()[0]).toBe('Closure pack');
    expect(document.body.textContent).not.toContain('Closure report');
    expect(phone().getAllByRole('listitem').map((li) => li.querySelector('strong')?.textContent)).toEqual(names());
  });

  it('leaves out kind, who, when and the version count when the API does not return them, with no empty element', async () => {
    const bare = withRows(fixture('desktop'), (rows) =>
      rows.map((r) => ({ line: r.line, name: r.name, version: r.version, test_template: r.test_template, template_id: r.template_id, revision: r.revision, can_upload: r.can_upload })),
    );
    answers.list = () => json(200, bare);
    await open();
    const text = document.body.textContent!;
    expect(text).not.toMatch(/Changed|PDF|DOCX|\d+ versions?/);
    const metas = Array.from(document.querySelectorAll('.setup-meta'));
    expect(metas.length).toBe(16);
    expect(metas.every((m) => /^Version \d+$/.test(m.textContent!))).toBe(true);
    expect(document.querySelectorAll('.setup-meta:empty')).toHaveLength(0);
  });

  it('shows a version as returned and the day with its year', async () => {
    answers.list = () => json(200, withRows(fixture('desktop'), (rows) => rows.map((r, i) => (i === 0 ? { ...r, version: '2026.2', updated_by: 'Ada Okafor', updated_at: '2025-06-30T10:00:00Z' } : r))));
    await open();
    expect(within(rowOf('Invoice')).getByText(/^Version 2026\.2/)).toBeTruthy();
    expect(within(rowOf('Invoice')).getByText('Changed by Ada Okafor, 30 Jun 2025')).toBeTruthy();
    expect(boardDay('2026-11-12T09:15:00+01:00', new Date('2026-11-14T09:00:00+01:00'))).toBe('12 Nov');
    expect(boardDay('2026-11-02T09:15:00+01:00', new Date('2026-11-14T09:00:00+01:00'))).toBe('02 Nov');
    expect(boardStamp('2026-11-12T10:40:00+01:00', new Date('2026-11-14T09:00:00+01:00'))).toBe('12 Nov, 10:40');
  });

  it('the phone shows a card per row: name, tag, line, meta and the upload button', async () => {
    await open();
    const card = cardOf('Closure report');
    expect(within(card).getByText('TEST TEMPLATE')).toBeTruthy();
    expect(within(card).getByText('Project closure')).toBeTruthy();
    expect(within(card).getByText('3 versions · Changed by Ada Okafor, 12 Nov')).toBeTruthy();
    expect(within(card).getByRole('button', { name: UPLOAD })).toBeTruthy();
    expect(phone().getAllByRole('listitem')).toHaveLength(8);
  });

  it('search filters the loaded rows by name and line without a request, and hints when more rows exist', async () => {
    await open();
    const search = desktop().getByRole('searchbox', { name: 'Search' });
    fireEvent.change(search, { target: { value: 'MINU' } });
    expect(names()).toEqual(['Minutes']);
    fireEvent.change(search, { target: { value: 'handoff' } });
    expect(names()).toEqual(['Minutes', 'RFP response']);
    fireEvent.change(search, { target: { value: 'zzz' } });
    expect(desktop().getByText('No templates match your search.')).toBeTruthy();
    expect(lists()).toHaveLength(1);
    expect(desktop().queryByText(/Searching the/)).toBeNull();
  });
});

describe('badge and copy follow test_template (AC 5)', () => {
  it('with every row true and no next_cursor: the banner, the phone line, and the count', async () => {
    await open();
    expect(desktop().getByText('Every document currently uses a test template. When PSL supplies its real template, upload it here; documents already sent keep the template they were made with.')).toBeTruthy();
    expect(phone().getByText('All 8 are test templates until PSL supplies its own.')).toBeTruthy();
    expect(desktop().getByText('8 TEMPLATES · 8 TEST')).toBeTruthy();
    expect(desktop().getByText('AS OF 12 NOV, 10:40')).toBeTruthy();
    expect(phone().getByText('AS OF 12 NOV, 10:40')).toBeTruthy();
  });

  it('with one row false: no banner and no "All n" line, that row has no tag and no claim, the others keep the tag', async () => {
    answers.list = () => json(200, withRows(fixture('desktop'), (rows) => rows.map((r) => (r.name === 'Minutes' ? { ...r, test_template: false } : r))));
    await open();
    expect(document.body.textContent).not.toMatch(/Every document currently|All \d+ are test templates/);
    expect(within(rowOf('Minutes')).queryByText('TEST TEMPLATE')).toBeNull();
    expect(within(cardOf('Minutes')).queryByText('TEST TEMPLATE')).toBeNull();
    expect(rowOf('Minutes').textContent).not.toMatch(/own|PSL/);
    expect(desktop().getAllByText('TEST TEMPLATE')).toHaveLength(7);
    expect(desktop().getByText('8 TEMPLATES · 7 TEST')).toBeTruthy();
    expect(within(rowOf('Minutes')).getByRole('button', { name: 'Upload a new version' })).toBeTruthy();
    expect(within(rowOf('Invoice')).getByRole('button', { name: UPLOAD })).toBeTruthy();
  });

  it('with next_cursor: no banner and the count reads SHOWN', async () => {
    const many = fixture('many');
    answers.list = () => json(200, { ...many, items: many.items.slice(0, 10), next_cursor: 'o:10' });
    await open();
    expect(document.body.textContent).not.toMatch(/Every document currently|All \d+ are test templates/);
    expect(desktop().getByText('10 SHOWN · 10 TEST')).toBeTruthy();
    fireEvent.change(desktop().getByRole('searchbox', { name: 'Search' }), { target: { value: 'in' } });
    expect(desktop().getByText('Searching the 10 shown')).toBeTruthy();
  });

  it('a test_template that is not a boolean reads as a test template', async () => {
    answers.list = () => json(200, withRows(fixture('desktop'), (rows) => rows.map((r, i) => (i === 0 ? ({ ...r, test_template: 'yes' } as unknown as TemplateRow) : r))));
    await open();
    expect(within(rowOf('Invoice')).getByText('TEST TEMPLATE')).toBeTruthy();
  });

  it('nothing in the Setup source sets or defaults test_template to false', () => {
    const dir = join(__dirname, '../src/features/setup');
    for (const file of readdirSync(dir).filter((f) => /\.tsx?$/.test(f))) {
      expect(readFileSync(join(dir, file), 'utf8'), file).not.toMatch(/test_template\s*(:|=|\?\?|\|\|)\s*false/);
    }
  });

  it('no template name is written in the Setup source', () => {
    const dir = join(__dirname, '../src/features/setup');
    for (const file of readdirSync(dir).filter((f) => /\.tsx?$/.test(f))) {
      expect(readFileSync(join(dir, file), 'utf8'), file).not.toMatch(/Statement of work|Weekly client report|Closure report/);
    }
  });
});

describe('upload gating (AC 6, 14)', () => {
  it('the readonly fixture has no upload control, no placeholder and no disabled button, and still shows the list and tags', async () => {
    answers.list = () => json(200, fixture('readonly'));
    await open();
    expect(screen.queryAllByRole('button', { name: /Upload/ })).toHaveLength(0);
    expect(document.querySelectorAll('.setup-table button:not(.psl-seg__opt), .setup-card button')).toHaveLength(0);
    expect(names()).toHaveLength(8);
    expect(desktop().getAllByText('TEST TEMPLATE')).toHaveLength(8);
    expect(document.body.textContent).not.toMatch(/not allowed|can’t upload|read-only/i);
  });

  it('a row needs template_id, can_upload true and a revision for the control', async () => {
    answers.list = () =>
      json(
        200,
        withRows(fixture('desktop'), (rows) => [
          { ...rows[0], can_upload: undefined },
          { ...rows[1], template_id: undefined },
          { ...rows[2], can_upload: false },
          rows[3],
        ]),
      );
    await open();
    expect(desktop().getAllByRole('button', { name: UPLOAD })).toHaveLength(1);
    expect(within(rowOf('Minutes')).getByRole('button', { name: UPLOAD })).toBeTruthy();
  });

  it('pm is not let in and makes no template call', async () => {
    answers.me = 'pm';
    render(
      <AppShell>
        <SetupLayoutFrame>
          <TemplatesPageView />
        </SetupLayoutFrame>
      </AppShell>,
    );
    await screen.findByText('This section isn’t open to your role.');
    expect(lists()).toHaveLength(0);
  });

  it('403 and 404 on the read show the not-open view with no template name; 401 the signed-out state; 5xx the error card', async () => {
    for (const status of [403, 404]) {
      answers.list = () => json(status, FORBIDDEN);
      const view = render(
        <AppShell>
          <SetupLayoutFrame>
            <TemplatesPageView />
          </SetupLayoutFrame>
        </AppShell>,
      );
      await screen.findByText('This section isn’t open to your role.');
      expect(document.body.textContent).not.toMatch(/Invoice|Templates/);
      expect(Array.from(document.querySelectorAll('h1')).map((h) => h.textContent)).toEqual(['Setup']);
      view.unmount();
    }
    answers.list = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    const signedOut = render(
      <AppShell>
        <SetupLayoutFrame>
          <TemplatesPageView />
        </SetupLayoutFrame>
      </AppShell>,
    );
    await waitFor(() => expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fsetup%2Ftemplates'));
    signedOut.unmount();
    let tries = 0;
    answers.list = () => (tries++ === 0 ? json(500, BOOM) : json(200, fixture('desktop')));
    await open();
    expect(screen.getByText('We couldn’t load the templates. Your work is safe; nothing was changed.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(names()).toHaveLength(8));
  });

  it('empty: the empty state and no banner, count or table; the frame stays on desktop', async () => {
    answers.list = () => json(200, fixture('empty'));
    await open();
    expect(desktop().getByText('No templates to show.')).toBeTruthy();
    expect(phone().getByText('No templates to show.')).toBeTruthy();
    expect(document.querySelector('table')).toBeNull();
    expect(document.body.textContent).not.toMatch(/TEMPLATES ·|test template|All \d+ are/);
    expect(frame().getByRole('tablist', { name: 'Setup' })).toBeTruthy();
  });
});

describe('the upload request (AC 7)', () => {
  it('posts to the template with the CSRF header and exactly expected_revision, filename, content_base64 and note', async () => {
    const live = liveList(withRows(fixture('desktop'), (rows) => rows));
    answers.list = live.list;
    answers.upload = live.upload;
    await open();
    const p = await openPanel('Closure report');
    const bytes = 'é€😀 template';
    choose(p, pdf('sow-v4.docx', bytes), '  Real SOW from legal.  ');
    expect(p.getByText('sow-v4.docx · 18 B')).toBeTruthy();
    send();
    await waitFor(() => expect(uploads()).toHaveLength(1));
    const call = uploads()[0];
    expect(call.path).toBe('/api/v1/setup/templates/T-08/versions');
    expect(call.csrf).toBe('mock-csrf-admin');
    expect(Object.keys(call.body!).sort()).toEqual(['content_base64', 'expected_revision', 'filename', 'note']);
    expect(call.body).toMatchObject({ expected_revision: 3, filename: 'sow-v4.docx', note: 'Real SOW from legal.' });
    expect(Buffer.from(call.body!.content_base64 as string, 'base64').toString('utf8')).toBe(bytes);
  });

  it('sends revision 0 as 0, and leaves a blank note out', async () => {
    answers.list = () => json(200, withRows(fixture('desktop'), (rows) => rows.map((r, i) => (i === 0 ? { ...r, revision: 0 } : r))));
    await open();
    const p = await openPanel('Invoice');
    choose(p, pdf(), '   ');
    send();
    await waitFor(() => expect(uploads()).toHaveLength(1));
    expect(Object.keys(uploads()[0].body!).sort()).toEqual(['content_base64', 'expected_revision', 'filename']);
    expect(uploads()[0].body!.expected_revision).toBe(0);
    expect(Buffer.from(uploads()[0].body!.content_base64 as string, 'base64')).toEqual(Buffer.from([0x25, 0x50, 0x44, 0x46]));
  });

  it('the panel has a labelled File input, a Note with a counter, Upload version (off until a file) and Cancel', async () => {
    await open();
    const p = await openPanel('Invoice');
    expect(p.getByLabelText('File').getAttribute('type')).toBe('file');
    expect(p.getByLabelText('Note (optional)').tagName).toBe('TEXTAREA');
    expect(p.getByText('0 / 2000')).toBeTruthy();
    expect(submit().disabled).toBe(true);
    choose(p, pdf());
    expect(submit().disabled).toBe(false);
    expect(document.body.textContent).not.toContain('This replaces the current version');
    expect(p.getByRole('button', { name: 'Cancel' })).toBeTruthy();
  });
});

describe('success (AC 8)', () => {
  it('closes the panel, reads once, shows the reloaded version, who and day, moves focus to the row and announces it', async () => {
    const live = liveList(fixture('desktop'));
    answers.list = live.list;
    answers.upload = live.upload;
    await open();
    const p = await openPanel('Invoice');
    choose(p, pdf());
    send();
    await waitFor(() => expect(announced()).toBe('Version 2 uploaded for Invoice'));
    expect(lists()).toHaveLength(2);
    expect(desktop().queryByRole('region', { name: /^Upload a version of/ })).toBeNull();
    const first = rowOf('Invoice');
    expect(within(first).getByText('Version 2 · PDF')).toBeTruthy();
    expect(within(first).getByText('1 version · Changed by Ada Okafor, 14 Nov')).toBeTruthy();
    expect(within(first).getByText('TEST TEMPLATE')).toBeTruthy();
    await waitFor(() => expect(document.activeElement?.textContent).toBe('Invoice'));
    await waitFor(() => expect(document.activeElement?.getAttribute('data-name-for')).toBe('T-01'));
  });

  it('shows the badge exactly as the reload returns it: false removes the tag with no extra claim, true keeps it', async () => {
    for (const flag of [false, true]) {
      calls = [];
      const live = liveList(fixture('desktop'));
      answers.list = live.list;
      answers.upload = (n, c) => {
        const res = live.upload(n, c);
        live.page.items[0].test_template = flag;
        return res;
      };
      const view = render(
        <AppShell>
          <SetupLayoutFrame>
            <TemplatesPageView />
          </SetupLayoutFrame>
        </AppShell>,
      );
      await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
      const p = await openPanel('Invoice');
      choose(p, pdf());
      send();
      await waitFor(() => expect(lists()).toHaveLength(2));
      await waitFor(() => expect(desktop().queryByRole('region', { name: /^Upload a version of/ })).toBeNull());
      expect(within(rowOf('Invoice')).queryByText('TEST TEMPLATE') !== null).toBe(flag);
      expect(rowOf('Invoice').textContent).not.toMatch(/PSL's own|PSL’s own|real template/);
      view.unmount();
    }
  });

  it('when the reload fails the row shows the 200 version and badge and the page says so', async () => {
    let uploaded = false;
    answers.list = () => (uploaded ? json(500, BOOM) : json(200, fixture('desktop')));
    answers.upload = () => {
      uploaded = true;
      return json(200, { template_id: 'T-01', version: '9', test_template: false, revision: 5 });
    };
    await open();
    const p = await openPanel('Invoice');
    choose(p, pdf());
    send();
    await waitFor(() => expect(desktop().getByText('Uploaded. We couldn’t refresh the list.')).toBeTruthy());
    expect(within(rowOf('Invoice')).getByText(/^Version 9/)).toBeTruthy();
    expect(within(rowOf('Invoice')).queryByText('TEST TEMPLATE')).toBeNull();
    expect(within(rowOf('Statement of work')).getByText('TEST TEMPLATE')).toBeTruthy();
  });
});

describe('stale (409) (AC 9)', () => {
  it('shows the API message, reads once, clears the file and note and closes; the next press sends nothing until a file is chosen, then carries the new revision', async () => {
    const live = liveList(fixture('desktop'));
    answers.list = live.list;
    answers.upload = (_, c) => {
      live.upload(0, c); // someone else uploaded first
      return json(409, STALE);
    };
    await open();
    const p = await openPanel('Invoice');
    choose(p, pdf(), 'my note');
    send();
    await waitFor(() => expect(desktop().getByText(STALE.message)).toBeTruthy());
    expect(lists()).toHaveLength(2);
    expect(desktop().queryByRole('region', { name: /^Upload a version of/ })).toBeNull();
    expect(within(rowOf('Invoice')).getByText(/^Version 2/)).toBeTruthy();
    const again = await openPanel('Invoice');
    expect((again.getByLabelText('Note (optional)') as HTMLTextAreaElement).value).toBe('');
    expect(submit().disabled).toBe(true);
    fireEvent.click(submit());
    expect(uploads()).toHaveLength(1);
    answers.upload = live.upload;
    choose(again, pdf('second.pdf'));
    send();
    await waitFor(() => expect(uploads()).toHaveLength(2));
    expect(uploads()[1].body).toMatchObject({ filename: 'second.pdf', expected_revision: 2 });
    expect(uploads()[1].body).not.toHaveProperty('note');
  });
});

describe('invalid (422) and client refusals (AC 10)', () => {
  it('marks the named fields, ties the messages, shows the alert, keeps the entries and needs no reload', async () => {
    answers.upload = () =>
      json(422, {
        code: 'invalid',
        message: 'Check these fields: filename, note.',
        fields: [
          { name: 'filename', message: 'That file type isn’t accepted.' },
          { name: 'note', message: 'The note can’t be saved.' },
        ],
      });
    await open();
    const p = await openPanel('Invoice');
    choose(p, pdf('bad.docx'), 'keep me');
    send();
    await waitFor(() => expect(p.getByRole('alert').textContent).toBe('Check these fields: filename, note.'));
    const file = p.getByLabelText('File');
    const note = p.getByLabelText('Note (optional)');
    expect(file.getAttribute('aria-invalid')).toBe('true');
    expect(note.getAttribute('aria-invalid')).toBe('true');
    expect(file.getAttribute('aria-describedby')).toContain(p.getByText('That file type isn’t accepted.').closest('small')!.id);
    expect(note.getAttribute('aria-describedby')).toContain(p.getByText('The note can’t be saved.').closest('span.psl-error')!.id);
    expect((note as HTMLTextAreaElement).value).toBe('keep me');
    expect(lists()).toHaveLength(1);
    expect(submit().disabled).toBe(false);
    answers.upload = () => json(200, { template_id: 'T-01', version: '2', test_template: true, revision: 2 });
    send();
    await waitFor(() => expect(uploads()).toHaveLength(2));
    expect(uploads()[1].body).toMatchObject({ filename: 'bad.docx', note: 'keep me' });
  });

  it('a 422 that names no field still shows the alert', async () => {
    answers.upload = () => json(422, { code: 'invalid', message: 'This file cannot be used.' });
    await open();
    const p = await openPanel('Invoice');
    choose(p, pdf());
    send();
    await waitFor(() => expect(p.getByRole('alert').textContent).toBe('This file cannot be used.'));
    expect(p.getByLabelText('File').getAttribute('aria-invalid')).toBeNull();
  });

  it('refuses a zero-byte file and a 2001-character note before any request', async () => {
    await open();
    const p = await openPanel('Invoice');
    choose(p, pdf('empty.pdf', new Uint8Array(0)));
    expect(p.getByText('That file is empty. Choose another file.')).toBeTruthy();
    expect(p.getByLabelText('File').getAttribute('aria-invalid')).toBe('true');
    expect(submit().disabled).toBe(true);
    fireEvent.click(submit());
    choose(p, pdf(), 'x'.repeat(2001));
    expect(p.getByText('The note can be up to 2000 characters.')).toBeTruthy();
    expect(submit().disabled).toBe(true);
    fireEvent.click(submit());
    fireEvent.change(p.getByLabelText('Note (optional)'), { target: { value: 'x'.repeat(2000) } });
    expect(submit().disabled).toBe(false);
    expect(uploads()).toHaveLength(0);
  });
});

describe('other failures (AC 11)', () => {
  it('401 on the write shows the signed-out state with next = this page', async () => {
    answers.upload = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open();
    choose(await openPanel('Invoice'), pdf());
    send();
    await waitFor(() => expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fsetup%2Ftemplates'));
    expect(lists()).toHaveLength(1);
  });

  it('403 on the write shows the message, reads, and the row loses its control when the right is withdrawn', async () => {
    let withdrawn = false;
    answers.list = () => json(200, withdrawn ? withRows(fixture('desktop'), (rows) => rows.map((r, i) => (i === 0 ? { ...r, can_upload: false } : r))) : fixture('desktop'));
    answers.upload = () => {
      withdrawn = true;
      return json(403, FORBIDDEN);
    };
    await open();
    choose(await openPanel('Invoice'), pdf());
    send();
    await waitFor(() => expect(desktop().getByText(FORBIDDEN.message)).toBeTruthy());
    expect(lists()).toHaveLength(2);
    expect(within(rowOf('Invoice')).queryByRole('button')).toBeNull();
    expect(desktop().queryByRole('region', { name: /^Upload a version of/ })).toBeNull();
  });

  it('403 or 404 on the write followed by a 403 read shows the not-open view with no template name', async () => {
    for (const status of [403, 404]) {
      calls = [];
      let reads = 0;
      answers.list = () => (reads++ === 0 ? json(200, fixture('desktop')) : json(403, FORBIDDEN));
      answers.upload = () => json(status, FORBIDDEN);
      const view = render(
        <AppShell>
          <SetupLayoutFrame>
            <TemplatesPageView />
          </SetupLayoutFrame>
        </AppShell>,
      );
      await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
      choose(await openPanel('Invoice'), pdf());
      send();
      await screen.findByText('This section isn’t open to your role.');
      expect(document.body.textContent).not.toContain('Invoice');
      view.unmount();
    }
  });

  it('a network error reads once, never resends, and lets the person press again with the reloaded revision when nothing changed', async () => {
    let failed = false;
    answers.upload = (n) => {
      if (n === 0) {
        failed = true;
        throw new TypeError('Failed to fetch');
      }
      return json(200, { template_id: 'T-01', version: '2', test_template: true, revision: 2 });
    };
    await open();
    const p = await openPanel('Invoice');
    choose(p, pdf(), 'n');
    send();
    await waitFor(() => expect(desktop().getByText(/^We couldn’t confirm the upload\. Nothing new is shown for this template/)).toBeTruthy());
    expect(failed).toBe(true);
    expect(uploads()).toHaveLength(1);
    expect(lists()).toHaveLength(2);
    expect((panel().getByLabelText('Note (optional)') as HTMLTextAreaElement).value).toBe('n');
    expect(submit().disabled).toBe(false);
    send();
    await waitFor(() => expect(uploads()).toHaveLength(2));
  });

  it('a 5xx whose reload shows a higher version says the upload went through and clears the selection', async () => {
    const live = liveList(fixture('desktop'));
    answers.list = live.list;
    answers.upload = (n, c) => {
      live.upload(n, c);
      return json(500, BOOM);
    };
    await open();
    choose(await openPanel('Invoice'), pdf());
    send();
    await waitFor(() => expect(screen.getByText('The upload went through.')).toBeTruthy());
    expect(uploads()).toHaveLength(1);
    expect(lists()).toHaveLength(2);
    expect(desktop().queryByRole('region', { name: /^Upload a version of/ })).toBeNull();
    expect(within(rowOf('Invoice')).getByText(/^Version 2/)).toBeTruthy();
  });

  it('when that reload fails too the upload stays off, and Try again only reads the list', async () => {
    let broken = false;
    answers.list = () => (broken ? json(500, BOOM) : json(200, fixture('desktop')));
    answers.upload = () => {
      broken = true;
      return json(500, BOOM);
    };
    await open();
    choose(await openPanel('Invoice'), pdf());
    send();
    await waitFor(() => expect(desktop().getByText(/^We couldn’t check whether the upload went through/)).toBeTruthy());
    expect(submit().disabled).toBe(true);
    fireEvent.click(submit());
    expect(uploads()).toHaveLength(1);
    broken = false;
    fireEvent.click(desktop().getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(desktop().queryByRole('button', { name: 'Try again' })).toBeNull());
    expect(uploads()).toHaveLength(1);
    expect(submit().disabled).toBe(false);
  });
});

describe('no double submit (AC 12)', () => {
  it('two presses in one tick send one POST, and the button is busy and reads Uploading… meanwhile', async () => {
    let release!: (r: Response) => void;
    answers.upload = () => new Promise<Response>((resolve) => (release = resolve));
    await open();
    const p = await openPanel('Invoice');
    choose(p, pdf());
    const button = submit();
    act(() => {
      button.click();
      button.click();
    });
    await waitFor(() => expect(uploads()).toHaveLength(1));
    await waitFor(() => expect(submit().textContent).toBe('Uploading…'));
    expect(submit().getAttribute('aria-busy')).toBe('true');
    expect((p.getByRole('button', { name: 'Cancel' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(submit());
    expect(uploads()).toHaveLength(1);
    await act(async () => release(json(200, { template_id: 'T-01', version: '2', test_template: true, revision: 2 })));
    await waitFor(() => expect(lists()).toHaveLength(2));
    expect(uploads()).toHaveLength(1);
  });

  it('opening another row closes the first panel and drops its file; nothing is sent', async () => {
    await open();
    const first = await openPanel('Invoice');
    choose(first, pdf(), 'first note');
    const second = await openPanel('Minutes');
    expect(desktop().getAllByRole('region', { name: /^Upload a version of/ })).toHaveLength(1);
    expect(desktop().getByRole('region', { name: 'Upload a version of Minutes' })).toBeTruthy();
    expect((second.getByLabelText('Note (optional)') as HTMLTextAreaElement).value).toBe('');
    expect(submit().disabled).toBe(true);
    fireEvent.click(within(rowOf('Invoice')).getByRole('button', { name: UPLOAD }));
    expect((panel().getByLabelText('Note (optional)') as HTMLTextAreaElement).value).toBe('');
    expect(uploads()).toHaveLength(0);
  });

  it('Cancel and Escape close the panel and return focus to the row button', async () => {
    await open();
    const p = await openPanel('Invoice');
    fireEvent.click(p.getByRole('button', { name: 'Cancel' }));
    expect(desktop().queryByRole('region', { name: /^Upload a version of/ })).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(within(rowOf('Invoice')).getByRole('button', { name: UPLOAD })));
    await openPanel('Minutes');
    fireEvent.keyDown(panel().getByLabelText('Note (optional)'), { key: 'Escape' });
    expect(desktop().queryByRole('region', { name: /^Upload a version of/ })).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(within(rowOf('Minutes')).getByRole('button', { name: UPLOAD })));
  });
});

describe('paging (AC 13)', () => {
  const many = fixture('many');
  const pageOf = (cursor: string | null) => (cursor ? { ...many, items: many.items.slice(50) } : { ...many, items: many.items.slice(0, 50), next_cursor: 'o:50' });

  it('Show more appears only with next_cursor, sends the cursor as returned and appends in order', async () => {
    answers.list = (_, c) => json(200, pageOf(new URLSearchParams(c.query).get('cursor')));
    await open();
    expect(names()).toHaveLength(10);
    // the server's page of 50 is already loaded: a larger choice shows its rows without a request
    fireEvent.click(desktop().getByRole('radio', { name: '50' }));
    expect(names()).toHaveLength(50);
    expect(lists()).toHaveLength(1);
    fireEvent.click(desktop().getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(names()).toHaveLength(60));
    expect(lists()[1].query).toBe('?cursor=o%3A50');
    expect(names()).toEqual(many.items.map((r) => r.name));
    expect(desktop().queryByRole('button', { name: 'Show more' })).toBeNull();
    expect(desktop().getByText('60 TEMPLATES · 60 TEST')).toBeTruthy();
  });

  it('a failed page keeps the rows and offers Show more again; an upload then reloads the first page', async () => {
    let failOnce = true;
    answers.list = (_, c) => {
      const cursor = new URLSearchParams(c.query).get('cursor');
      if (cursor && failOnce) {
        failOnce = false;
        return json(500, BOOM);
      }
      return json(200, pageOf(cursor));
    };
    answers.upload = (_, c) => json(200, { template_id: decodeURIComponent(c.path.split('/')[5]), version: '2', test_template: true, revision: 2 });
    await open();
    fireEvent.click(desktop().getByRole('radio', { name: '50' }));
    fireEvent.click(desktop().getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(desktop().getByText('We couldn’t load more. Choose Show more to try again.')).toBeTruthy());
    expect(names()).toHaveLength(50);
    fireEvent.click(desktop().getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(names()).toHaveLength(60));
    choose(await openPanel('Sample template 1'), pdf());
    send();
    // the first page is read again, and the rows the person had asked for are fetched back by cursor
    await waitFor(() => expect(lists().slice(-2).map((c) => c.query)).toEqual(['', '?cursor=o%3A50']));
    await waitFor(() => expect(names()).toHaveLength(60));
  });
});

describe('titles, phone bar and tabs (AC 15, 16)', () => {
  it('one h1 per width: the frame title on desktop, "Templates" on the phone, with the bar link named Setup', async () => {
    await open();
    expect(frame().getAllByRole('heading', { level: 1 }).map((h) => h.textContent)).toEqual(['Roles, rules and delegation']);
    expect(frame().getByRole('heading', { level: 1 }).className).toBe('cmp-page-title cmp-page-title--34');
    expect(phone().getAllByRole('heading', { level: 1 }).map((h) => h.textContent)).toEqual(['Templates']);
    expect(phone().getByRole('heading', { level: 1 }).className).toBe('cmp-page-title cmp-page-title--p22');
    const back = await within(phoneBar()).findByRole('link', { name: 'Back to Setup' });
    expect(back.textContent).toBe('← Setup');
    expect(phone().queryByRole('link')).toBeNull();
  });

  it('the Templates tab is current, the other six are plain tabs, and no tab has a badge', async () => {
    await open();
    const tabs = within(screen.getByRole('tablist', { name: 'Setup' })).getAllByRole('tab');
    expect(tabs.map((t) => t.textContent)).toEqual(['Roles', 'Rules', 'Costing rule', 'Delegation', 'Payroll visibility', 'Staff accounts', 'Templates']);
    expect(tabs.filter((t) => t.getAttribute('aria-selected') === 'true').map((t) => t.textContent)).toEqual(['Templates']);
    expect(document.querySelectorAll('.setup-tabs .psl-badge')).toHaveLength(0);
  });
});
