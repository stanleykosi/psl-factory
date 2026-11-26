// F-118: the closure model's rules without a page: how each check is worded, which state the page is in, what may be sent from which
// read, and what is refused before any request. The reads are the live-shaped mock's own answers.
import { describe, expect, it } from 'vitest';

import {
  checkFields, closureCommands, closureNotice, closureSections, debtItem, debtSection, decideHeld, decisionTask, emptyFinance, financeHeld, headline, IDS, previousReport, replaceHeld, stateOf, TEXT,
  type Check, type Checklist, type FinanceRead, type HistoryRow, type Readback,
} from '@/features/delivery-closure/closureModel';

// @ts-expect-error plain ESM module without type declarations
import { closureLive } from '../mock/closure-live.mjs';

const get = (path: string) => {
  const [status, body] = closureLive({ method: 'get', url: new URL(`http://mock${path}`), scenario: undefined, csrfOk: true, persona: 'finance_lead' }) as [number, unknown];
  return status === 200 ? structuredClone(body) : null;
};
const fixture = (id: number): Readback => {
  const item = get(`/api/v1/work/${id}`) as { tasks: Readback['work'] extends infer W ? (W extends { tasks: infer T } ? T : never) : never; revision: number; case_revision: number; state: never };
  const dossier = id + 800;
  return {
    caseId: `00000000-0000-4000-8000-00000000${id}`,
    dossierId: dossier,
    checklist: get(`/api/v1/projects/00000000-0000-4000-8000-00000000${id}/delivery/${dossier}/closure-checklist`) as Checklist,
    work: { revision: item.revision, case_revision: item.case_revision, state: item.state, tasks: item.tasks },
    history: (get(`/api/v1/work/${id}/history`) as { items: HistoryRow[] }).items,
    finance: get(`/api/v1/projects/00000000-0000-4000-8000-00000000${id}/delivery/${dossier}/finance-confirmation`) as FinanceRead | null,
    financeEvidence: [],
    decision: null,
    failed: [],
  };
};
const ctx = { workId: 6204, revision: 8 };
const flat = (rb: Readback, state = 'waiting' as never) => closureSections(rb, { state }).flatMap((s) => s.items.map((i) => [i.text, i.label, i.detail, i.value, i.tag?.label, i.cite_label].filter(Boolean).join(' ')));
const ids = { version_id: 9601, evidence_id: 9602 };

describe('the check words (nothing here decides access)', () => {
  const base: Check = { key: 'go_live', title: 'Go-live acceptance', status: 'current', summary: 's', references: [], finding: null };
  it('maps all six statuses; unknown and unavailable are never Done', () => {
    expect(checkFields({ ...base, status: 'current' })).toEqual({ status: 'done' });
    expect(checkFields({ ...base, status: 'recorded' })).toEqual({ status: 'done' });
    expect(checkFields({ ...base, status: 'held' })).toEqual({ status: 'not_yet' });
    expect(checkFields({ ...base, status: 'unknown' })).toEqual({ status: 'unknown' });
    expect(checkFields({ ...base, status: 'closed' })).toEqual({ tag: { label: 'Closed', tone: 'verified' } });
    expect(checkFields({ ...base, status: 'unavailable' })).toEqual({ tag: { label: 'Not available', tone: 'neutral' } });
    expect(checkFields({ ...base, key: 'finance', status: 'current' })).toEqual({ tag: { label: 'Confirmed', tone: 'verified' } });
    expect(checkFields({ ...base, key: 'finance', status: 'unknown' })).toEqual({ status: 'unknown' });
    for (const s of ['unknown', 'unavailable', 'held'] as const) expect(checkFields({ ...base, status: s }).status).not.toBe('done');
  });
  it('6201 draws all eight live titles, the held finding, a finance sub-line and no record count for no records', () => {
    const rows = flat(fixture(6201));
    expect(rows.filter((r) => /^(Current project scope|Go-live acceptance|Release stability|Project archive|Support handover|Retrospective|Finance notification coverage|PM closure report)/.test(r))).toHaveLength(8);
    expect(rows.join('|')).toMatch(/Retrospective .*No retrospective saved/);
    expect(rows.join('|')).toMatch(/Finance notification coverage Milestone notifications confirmed by Finance/);
    expect(rows.find((r) => r.startsWith('PM closure report'))).not.toMatch(/\d+ records?/);
    expect(rows.join('|')).toMatch(/Go-live acceptance Go-live accepted · Current recorded evidence is available 1 record/);
  });
});

describe('the state', () => {
  it('maps each fixture to its state', () => {
    expect([6201, 6202, 6203, 6204, 6205, 6206].map((id) => stateOf(fixture(id)))).toEqual(['blocked', 'ready', 'awaiting', 'decision', 'returned', 'closed']);
  });
  it('the headline says Not yet with the first held finding as the next line, and the Head of PMO decides for a person who cannot', () => {
    expect(headline(fixture(6201), 'waiting')).toMatchObject({ label: 'Closure · Not yet', next: 'No retrospective saved' });
    expect(headline(fixture(6203), 'waiting')).toMatchObject({ label: 'Closure · Awaiting Head of PMO', next: 'The Head of PMO decides on closure.' });
    expect(headline(fixture(6204), 'action_needed').label).toBe('Closure · Waiting for your decision');
  });
  it('a returned closure names who, when and why from the history row, and only what the row gives', () => {
    expect(headline(fixture(6205), 'action_needed').detail).toBe('Ada Okafor returned closure on 24 Nov: “Add the client’s sign-off on the hypercare summary to the report.”');
    const rb = fixture(6205);
    rb.history = rb.history.map((r) => ({ ...r, reason: undefined }));
    expect(headline(rb, 'action_needed').detail).toBe('Ada Okafor returned closure on 24 Nov');
    rb.history = [];
    expect(stateOf(rb)).toBe('ready');
    expect(headline(rb, 'action_needed').detail).toBeNull();
  });
  it('after the report is replaced (state moved on) it is no longer returned', () => {
    const rb = fixture(6205);
    rb.work!.state = 'waiting';
    expect(stateOf(rb)).not.toBe('returned');
  });
  it('closed says Verified only when the item\'s state is verified', () => {
    expect(headline(fixture(6206), 'verified').detail).toBe('Verified');
    expect(headline(fixture(6206), 'processing').detail).toBeNull();
    const rb = fixture(6206);
    rb.history = [{ entry_id: 1, at: '2026-11-25T12:00:00Z', station: 'Closure review', status: 'approve', actor_kind: 'person', actor: 'Tunde Bello' }];
    expect(headline(rb, 'verified')).toMatchObject({ label: 'Closed 25 Nov 2026', detail: 'Closed by Tunde Bello · Verified' });
  });
  it('says nothing about read-only, Support contract or debts being confirmed', () => {
    for (const id of [6201, 6204, 6205, 6206, 6207]) expect(flat(fixture(id), 'verified' as never).join('|')).not.toMatch(/read-only|Support contract|Moved to Closed|debts? (are |is )?confirmed|Tola/i);
  });
});

describe('still open after closure', () => {
  it('shows the amount, "Amount not recorded" for a null amount (never 0 or blank), the date and the limited note', () => {
    const s = debtSection(fixture(6206).checklist.debt)!;
    expect(s.title).toBe('Still open after closure');
    expect(s.coverage).toBe('As of 20 Nov 2026 · List is limited; more may exist.');
    expect(s.items.map((i) => [i.label, i.value])).toEqual([['INV-0533', '₦1,250,000.00'], ['INV-0540', 'Amount not recorded']]);
    expect(JSON.stringify(s)).not.toMatch(/"value":"(0|₦0\.00)?"/);
  });
  it('an amount the formatter cannot read is shown as served, not as unknown', () => {
    expect(debtItem({ reference: 'INV-1', currency: 'USD', basis: 'b', owed: '12.5', api_url: 'x' }, 0).value).toBe('USD 12.5');
  });
  it('no open invoices says so with the date; a null debt draws no section at all', () => {
    expect(debtSection(fixture(6207).checklist.debt)!.items.map((i) => i.text)).toEqual(['No open invoices recorded as of 20 Nov 2026.']);
    expect(debtSection(null)).toBeNull();
    expect(closureSections(fixture(6208), { state: 'verified' }).some((s) => s.key === 'debt')).toBe(false);
    expect(closureSections(fixture(6204), { state: 'waiting' }).some((s) => s.key === 'debt')).toBe(false);
    expect(closureSections(fixture(6206), { state: 'verified' }).some((s) => s.key === 'debt')).toBe(true);
  });
});

describe('the Finance block', () => {
  it('lists the milestones as served, a finding as the reason, and Confirmed with no form once confirmed', () => {
    const sec = (id: number) => closureSections(fixture(id), { state: 'waiting' }).find((s) => s.key === 'finance');
    expect(sec(6204)!.title).toBe('Finance confirmation: milestone notifications');
    expect(sec(6204)!.items.map((i) => `${i.text} ${i.detail}`)).toEqual(['Milestone 31 Receipt 71', 'Milestone 32 Receipt 72']);
    expect(sec(6203)!.items.map((i) => i.text)).toEqual(['Receipt missing for milestone 3']);
    expect(sec(6201)).toBeUndefined();
    const confirmed = fixture(6204);
    confirmed.finance!.confirmation_id = 5;
    expect(closureSections(confirmed, { state: 'waiting' }).find((s) => s.key === 'finance')!.items[0].text).toBe('Confirmed');
    expect(closureCommands(confirmed, ctx).some((c) => c.id === IDS.finance)).toBe(false);
  });
  it('holds until the box is ticked, a served proof is chosen and a note is typed; a proof not on the list is refused', () => {
    const rb = fixture(6204);
    expect(financeHeld(rb, emptyFinance())).toMatch(/Tick/);
    expect(financeHeld(rb, { complete: true, proof: undefined, note: 'x' })).toBe(TEXT.noFinanceProof);
    rb.financeEvidence = [{ id: 9701, label: 'Receipt review' }];
    expect(financeHeld(rb, { complete: true, proof: '1', note: 'x' })).toMatch(/Choose a Finance proof/);
    expect(financeHeld(rb, { complete: true, proof: '9701', note: '  ' })).toMatch(/note/);
    expect(financeHeld(rb, { complete: true, proof: '9701', note: 'Checked' })).toBeNull();
  });
});

describe('the descriptors', () => {
  it('decide: described only for a task this person may decide; held until both ids are served; the body has no action and no key', () => {
    expect(closureCommands(fixture(6203), ctx).some((c) => c.id === IDS.decide)).toBe(false);
    expect(closureCommands(fixture(6206), ctx).some((c) => c.id === IDS.decide)).toBe(false);
    const held = closureCommands(fixture(6204), ctx).find((c) => c.id === IDS.decide)!;
    expect(held.disabledReason).toBe(TEXT.noDecision);
    const rb = fixture(6204);
    rb.decision = ids;
    const c = closureCommands(rb, ctx).find((x) => x.id === IDS.decide)!;
    expect(c.disabledReason).toBeUndefined();
    expect(c.url).toBe('/api/v1/work/6204/reviews');
    expect(c.successStatuses).toEqual([200]);
    expect(c.idempotency).toEqual({ field: null, value: null });
    expect(c.body({ verdict: 'approve', note: ' as typed ', action: 'sneaky' })).toEqual({ kind: 'closure', version_id: 9601, evidence_id: 9602, expected_revision: 8, case_revision: 41, verdict: 'approve', note: ' as typed ' });
  });
  it('a null token disables every write with "Reload to continue" and stays null in the body', () => {
    const rb = fixture(6204);
    rb.decision = ids;
    rb.work!.revision = null;
    const c = closureCommands(rb, ctx).find((x) => x.id === IDS.decide)!;
    expect(c.disabledReason).toBe('Reload to continue');
    expect(c.body({ verdict: 'approve', note: '' }).expected_revision).toBeNull();
    const noCase = fixture(6204);
    noCase.decision = ids;
    noCase.work!.case_revision = null;
    expect(closureCommands(noCase, ctx).find((x) => x.id === IDS.decide)!.disabledReason).toBe('Reload to continue');
    expect(closureCommands(rb, { workId: 6204, revision: null }).find((x) => x.id === IDS.decide)!.disabledReason).toBe('Reload to continue');
    const failed = fixture(6204);
    failed.work = null;
    expect(closureCommands(failed, ctx).some((x) => x.id === IDS.decide)).toBe(false);
  });
  it('reject is never offered; only the verdicts the task lists', () => {
    const rb = fixture(6204);
    rb.work!.tasks[0].verdicts = ['approve', 'reject'];
    expect(decisionTask(rb.work)!.verdicts).toEqual(['approve']);
    rb.work!.tasks[0].verdicts = ['reject'];
    expect(decisionTask(rb.work)).toBeNull();
  });
  it('the return needs a note; the approval does not; nothing is trimmed in what is sent', () => {
    expect(decideHeld('return', '  ')).toMatch(/note/);
    expect(decideHeld('return', 'x')).toBeNull();
    expect(decideHeld('approve', '')).toBeNull();
    expect(decideHeld('return', 'x'.repeat(4001))).toMatch(/4000/);
  });
  it('replace: described in the returned state with the report evidence from the check; a null previous stays null', () => {
    expect(closureCommands(fixture(6204), ctx).some((c) => c.id === IDS.replace)).toBe(false);
    const rb = fixture(6205);
    expect(previousReport(rb.checklist)).toBe(107);
    const c = closureCommands(rb, { workId: 6205, revision: 8 }).find((x) => x.id === IDS.replace)!;
    expect(c.url).toBe('/api/v1/work/6205/closure-report');
    expect(c.successStatuses).toEqual([201]);
    expect(c.body({ report_text: 'r', source_reference: 's', reason: 'why' })).toEqual({ previous_evidence_id: 107, expected_revision: 8, case_revision: 41, report_text: 'r', source_reference: 's', reason: 'why' });
    rb.checklist.checks = rb.checklist.checks.map((k) => (k.key === 'report' ? { ...k, status: 'unknown', references: [] } : k));
    expect(closureCommands(rb, { workId: 6205, revision: 8 }).find((x) => x.id === IDS.replace)!.body({}).previous_evidence_id).toBeNull();
    rb.checklist.checks = rb.checklist.checks.map((k) => (k.key === 'report' ? { ...k, status: 'current', references: [1, 2] } : k));
    expect(previousReport(rb.checklist)).toBeNull();
  });
  it('replace: 16 000 characters pass, 16 001 are refused before sending; blanks are refused', () => {
    const ok = { report: 'x'.repeat(16000), source: 's', reason: 'r' };
    expect(replaceHeld(ok)).toBeNull();
    expect(replaceHeld({ ...ok, report: 'x'.repeat(16001) })).toMatch(/16,000/);
    expect(replaceHeld({ ...ok, report: ' ' })).toMatch(/report text/);
    expect(replaceHeld({ ...ok, source: '' })).toMatch(/where/);
    expect(replaceHeld({ ...ok, reason: ' ' })).toMatch(/why/);
    expect(replaceHeld({ ...ok, source: 'x'.repeat(161) })).toMatch(/160/);
  });
  it('finance: the exact revision of its own read, every listed milestone, complete true, and the reason a finding gives', () => {
    const c = closureCommands(fixture(6204), ctx).find((x) => x.id === IDS.finance)!;
    expect(c.url).toBe('/api/v1/projects/00000000-0000-4000-8000-000000006204/delivery/7004/finance-confirmation');
    expect(c.successStatuses).toEqual([201]);
    expect(c.idempotency.field).toBeNull();
    expect(c.body({ evidence_id: 9701, note: 'n' })).toEqual({ milestone_ids: [31, 32], inventory_complete: true, revision: 41, evidence_id: 9701, note: 'n' });
    expect(closureCommands(fixture(6203), ctx).find((x) => x.id === IDS.finance)!.disabledReason).toBe('Receipt missing for milestone 3');
    expect(closureCommands(fixture(6201), ctx).some((x) => x.id === IDS.finance)).toBe(false);
  });
});

describe('the words under a write', () => {
  const err = (text: string, detail?: string) => ({ kind: 'error' as const, text, ...(detail ? { detail } : {}) });
  it('a changed record, a refusal to decide and a too-large report get the page\'s words and no server reason', () => {
    const changed = err('This changed while you were working. Showing the latest version.', 'Someone changed this.');
    expect(closureNotice(changed, IDS.decide)).toEqual({ text: TEXT.stale });
    expect(closureNotice(changed, IDS.finance)).toEqual({ text: TEXT.financeStale });
    expect(closureNotice(err('You can’t do this.', 'Only the Head of PMO can do this.'), IDS.decide)).toEqual({ text: TEXT.cantDecide });
    expect(closureNotice(err('You can’t do this.', 'x'), IDS.replace)).toEqual({ text: 'You can’t do this.', detail: 'x' });
    expect(closureNotice(err('That is too large to send.'), IDS.replace)).toEqual({ text: TEXT.tooLong });
    expect(closureNotice(err('Press the button again.'), IDS.decide)).toEqual({ text: 'Press the button again.' });
  });
});
