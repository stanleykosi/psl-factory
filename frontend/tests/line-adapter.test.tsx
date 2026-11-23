// @vitest-environment jsdom
// F-85: the per-line adapter (types, registry, command descriptors) and the weekly report adapter, read only.
import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { LiveWeeklyReport } from '@/api/types';
import { adapterFor, isPanelUrl, makeCommand, registerLineAdapter, type LineAdapter, type LineContext } from '@/features/workspace/adapter';
import type { Section } from '@/features/workspace/labels';
import { SectionView } from '@/features/workspace/Sections';
import { NOT_RECORDED, weeklyReportAdapter } from '@/features/workspace/weeklyReportAdapter';

// @ts-expect-error plain ESM module without type declarations
import { workLive } from '../mock/work-live.mjs';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const ctx: LineContext = { workId: 4102, caseId: 'c1', revision: 3, caseRevision: 7 };
const report = (id = 4102) => (workLive({ method: 'get', url: new URL(`/api/v1/work/${id}/weekly-report`, 'http://m.local'), csrfOk: true, persona: 'finance_lead' }) as [number, LiveWeeklyReport])[1];

describe('the adapter interface (AC16, AC17)', () => {
  it('a registered fake adapter reads its panel, gives Sections the renderer draws, and describes a command', async () => {
    const sections: Section[] = [{ key: 's', kind: 'text', title: 'Fake panel', items: [{ id: 'a', text: 'Hello from the line' }] }];
    const fake: LineAdapter<{ n: number }> = {
      key: 'fake-line',
      read: async () => ({ n: 1 }),
      sections: () => sections,
      commands: (_r, c) => [makeCommand({ id: 'fake-line.send', label: 'Send', url: `/api/v1/work/${c.workId}/fake`, tokens: { expected_revision: c.revision, case_revision: c.caseRevision }, keyField: 'operation', successStatuses: [200, 202] })],
    };
    registerLineAdapter(fake as LineAdapter);
    const adapter = adapterFor('fake-line')!;
    const readback = await adapter.read({ key: 'fake-line', url: '/api/v1/work/4102/fake' });
    render(<>{adapter.sections(readback, ctx).map((s) => <SectionView key={s.key} section={s} level={2} />)}</>);
    expect(screen.getByRole('heading', { name: 'Fake panel' })).toBeTruthy();
    expect(screen.getByText('Hello from the line')).toBeTruthy();
    const [command] = adapter.commands!(readback, ctx);
    const body = command.body({ note: 'x' });
    expect(body).toMatchObject({ action: 'send', expected_revision: 3, case_revision: 7, note: 'x' });
    expect(body.operation).toMatch(UUID);
    expect(command.idempotency).toEqual({ field: 'operation', value: body.operation });
    expect(command.method).toBe('POST');
    expect(adapterFor('nothing-registered')).toBeUndefined();
  });

  it('a null token stays null, never 0; a line with no key field has no key', () => {
    const command = makeCommand({ id: 'line.act', label: 'Act', url: '/api/v1/work/1/x', tokens: { expected_revision: null, case_revision: 4 }, successStatuses: [200] });
    expect(command.idempotency).toEqual({ field: null, value: null });
    const body = command.body({});
    expect(body).toEqual({ action: 'act', expected_revision: null, case_revision: 4 });
    expect(Object.keys(body)).not.toContain('operation');
  });

  it('the descriptor\'s own fields win over inputs: action, tokens and the key cannot be overridden', () => {
    const command = makeCommand({ id: 'line.act', label: 'Act', url: '/api/v1/work/1/x', tokens: { expected_revision: 3, case_revision: null }, keyField: 'operation', successStatuses: [200] });
    const body = command.body({ action: 'evil', expected_revision: 99, case_revision: 98, operation: 'mine', note: 'kept' });
    expect(body).toMatchObject({ action: 'act', expected_revision: 3, case_revision: null, operation: command.idempotency.value, note: 'kept' });
  });

  it('a body with action: null carries no action', () => {
    const command = makeCommand({ id: 'work.background.pause', label: 'Pause', url: '/api/v1/work/1/background', tokens: { expected_revision: 7 }, action: null, successStatuses: [202] });
    expect(command.body({ enabled: false })).toEqual({ expected_revision: 7, enabled: false });
  });

  it('each descriptor makes its own key, once', () => {
    const make = () => makeCommand({ id: 'a.b', label: 'B', url: '/api/v1/x', tokens: {}, keyField: 'key', successStatuses: [201] });
    const one = make();
    expect(one.body({}).key).toBe(one.body({}).key);
    expect(make().idempotency.value).not.toBe(one.idempotency.value);
  });

  it('reads only this site’s API paths', () => {
    expect(isPanelUrl('/api/v1/work/4102/weekly-report')).toBe(true);
    for (const bad of ['https://evil.example/api/v1/x', '//evil.example/api/v1/x', '/api/v1/../admin', '/api/v1//x', 'api/v1/x', '/other/x', '/api/v1/x?a=b', ' /api/v1/x', '/API/v1/x', 'javascript:alert(1)']) {
      expect(isPanelUrl(bad)).toBe(false);
    }
  });
});

describe('the weekly report adapter (AC18, AC21)', () => {
  let fetchStub: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    fetchStub = vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      const id = Number(url.pathname.split('/')[4]);
      return new Response(JSON.stringify(report(id)), { status: 200, headers: { 'Content-Type': 'application/json' } });
    });
    vi.stubGlobal('fetch', fetchStub);
  });
  afterEach(() => vi.unstubAllGlobals());

  const draw = (r: LiveWeeklyReport) => render(<>{weeklyReportAdapter.sections(r, ctx).map((s) => <SectionView key={s.key} section={s} level={2} />)}</>);

  it('reads its panel route and is registered under weekly-report', async () => {
    expect(adapterFor('weekly-report')).toBe(weeklyReportAdapter);
    const readback = await weeklyReportAdapter.read({ key: 'weekly-report', url: '/api/v1/work/4102/weekly-report' });
    expect(readback.expected_revision).toBe(3);
    expect(new URL(fetchStub.mock.calls[0][0].url).pathname).toBe('/api/v1/work/4102/weekly-report');
    await expect(weeklyReportAdapter.read({ key: 'weekly-report', url: 'https://evil.example/api/v1/x' })).rejects.toBeTruthy();
    expect(fetchStub).toHaveBeenCalledTimes(1);
  });

  it('draws the period, the four parts with record counts, recipients with receipt state and the next action', () => {
    draw(report());
    expect(screen.getByRole('heading', { name: 'Period' })).toBeTruthy();
    expect(screen.getByText(/Build is on track\./)).toBeTruthy();
    expect(screen.getByText('3 records cited')).toBeTruthy();
    expect(screen.getByText('1 record cited')).toBeTruthy();
    expect(screen.getByText('0 records cited')).toBeTruthy();
    expect(screen.getByText('Amaka Eze')).toBeTruthy();
    expect(screen.getByText('Receipt recorded')).toBeTruthy();
    expect(screen.getByText('No receipt yet')).toBeTruthy();
    expect(screen.getByText('Wait for the client to confirm receipt.')).toBeTruthy();
  });

  it('null editable_parts and no draft draw no parts section; a draft with parts is drawn', () => {
    draw(report(4107));
    expect(screen.queryByRole('heading', { name: /Report parts|Draft/ })).toBeNull();
    expect(screen.queryByText(/cited/)).toBeNull();
  });

  it('shows the draft parts when editable_parts is null', () => {
    const base = report();
    const parts = base.editable_parts!;
    draw({ ...base, editable_parts: null, draft: { id: 1, values: { selection: { template_id: null, content_id: null, start_at: 'a', end_at: 'b' }, parts, reference: 'r', key: 'k', background: false, reason: '' } } });
    expect(screen.getByRole('heading', { name: 'Draft' })).toBeTruthy();
  });

  it('says Returned to you without a note when a return review exists; unknown values read Not recorded', () => {
    draw({ ...report(4107), return_review_id: 55, selection: { start_at: '', end_at: '', template_id: null, content_id: null } });
    expect(screen.getByText('Returned to you')).toBeTruthy();
    expect(screen.getAllByText(NOT_RECORDED).length).toBeGreaterThan(0);
  });

  it('describes correct with its tokens, and a reason when can_correct is false; draws no button', () => {
    const [on] = weeklyReportAdapter.commands!(report(), ctx);
    expect(on.id).toBe('weekly-report.correct');
    expect(on.disabledReason).toBeUndefined();
    expect(on.url).toBe('/api/v1/work/4102/weekly-report');
    expect(on.successStatuses).toEqual([201]);
    expect(on.idempotency.field).toBeNull();
    expect(on.body({ reason: 'typo' })).toMatchObject({ action: 'correct', expected_revision: 3, case_revision: 7, reason: 'typo' });
    const [off] = weeklyReportAdapter.commands!(report(4107), ctx);
    expect(off.disabledReason).toBeTruthy();
    draw(report());
    expect(screen.queryByRole('button')).toBeNull();
  });
});
