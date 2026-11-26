// F-116: the archive model: groups and counts, the status sentence, the group state words, the sources and the command descriptors (tokens, no key, null stays null).
import { describe, expect, it } from 'vitest';

import { archiveCommands, archiveSections, canLookup, canRetry, defaultSources, groupState, groupsOf, startHeld, statusSentence, type Archive, type ArchiveFile } from '@/features/delivery-archive/archiveModel';

const file = (id: number, state: NonNullable<ArchiveFile['job']>['state'] | null, patch: Partial<ArchiveFile> = {}): ArchiveFile => ({
  id,
  name: `f${id}.pdf`,
  status: 'x',
  job: state === null ? null : { id: 900 + id, revision: 3, state },
  group: 'Legal',
  source_id: null,
  source_kind: null,
  actions: [],
  receipt: null,
  ...patch,
});
const archive = (files: ArchiveFile[], patch: Partial<Archive> = {}): Archive => ({
  expected_revision: 7,
  case_revision: 41,
  plan_id: 1,
  store: null,
  finding: 'The archive is not verified yet.',
  verified: false,
  can_reserve: false,
  limited: false,
  required_source_ids: [],
  sources: [],
  files,
  ...patch,
});

describe('groups', () => {
  it('draws the groups as served, a group the page did not know included, with counts that add up to the files', () => {
    const a = archive([file(1, 'confirmed'), file(2, 'confirmed', { group: 'Planning' }), file(3, 'confirmed'), file(4, 'unknown', { group: 'Brand new group' })]);
    const groups = groupsOf(a);
    expect(groups.map((g) => g.name)).toEqual(['Legal', 'Planning', 'Brand new group']);
    expect(groups.reduce((n, g) => n + g.files.length, 0)).toBe(a.files.length);
    expect(groups[0].files).toHaveLength(2);
  });
  it('a group of six not confirmed and three archived headlines the worst state first, with counts', () => {
    const files = [...Array.from({ length: 6 }, (_, i) => file(i, 'unknown')), ...Array.from({ length: 3 }, (_, i) => file(10 + i, 'confirmed'))];
    expect(groupState(files)).toBe('Not confirmed · 6, Archived · 3');
  });
  it('one state alone: Archived, Copying (waiting or leased), Not started (no job); the counted states always carry N', () => {
    expect(groupState([file(1, 'confirmed'), file(2, 'confirmed')])).toBe('Archived');
    expect(groupState([file(1, 'pending'), file(2, 'leased')])).toBe('Copying');
    expect(groupState([file(1, null), file(2, null)])).toBe('Not started');
    expect(groupState([file(1, 'missing')])).toBe('Missing · 1');
    expect(groupState([file(1, 'held'), file(2, 'held')])).toBe('On hold · 2');
  });
  it('orders a mix worst first: not confirmed, missing, on hold, copying, archived', () => {
    const files = [file(1, 'confirmed'), file(2, 'leased'), file(3, 'held'), file(4, 'missing'), file(5, 'unknown')];
    expect(groupState(files)).toBe('Not confirmed · 1, Missing · 1, On hold · 1, Copying · 1, Archived · 1');
  });
});

describe('the status sentence', () => {
  const confirmed = Array.from({ length: 42 }, (_, i) => file(i, 'confirmed'));
  it('says archived and verified only from `verified`', () => {
    expect(statusSentence(archive(confirmed, { verified: true }), 'verified')).toBe('Archived and verified: 42 files, each matched in the archive index.');
    expect(statusSentence(archive(confirmed, { verified: false }), 'action_needed')).not.toMatch(/verified:/);
    expect(statusSentence(archive(confirmed, { verified: false }), 'action_needed')).toBe('The archive is not verified yet.');
  });
  it('working: copied over total, from the job states', () => {
    const files = [...confirmed.slice(0, 28), ...Array.from({ length: 10 }, (_, i) => file(100 + i, 'leased')), ...Array.from({ length: 4 }, (_, i) => file(200 + i, 'pending'))];
    expect(statusSentence(archive(files), 'processing')).toBe('Archiving in progress. 28 of 42 files copied.');
  });
  it('uncertain: the files the store did not confirm; the work state alone says the result is not confirmed', () => {
    const files = [...Array.from({ length: 6 }, (_, i) => file(i, 'unknown')), ...confirmed.slice(0, 36)];
    expect(statusSentence(archive(files), 'effect_uncertain')).toBe('The archive store didn’t confirm 6 of 42 files. They won’t be copied again until someone checks what arrived.');
    expect(statusSentence(archive(confirmed), 'effect_uncertain')).toBe('The archive result is not confirmed.');
    expect(statusSentence(archive(confirmed), 'awaiting_reconciliation')).toBe('The archive result is not confirmed.');
  });
  it('held files add their count; no files reads Nothing is waiting, or nothing when a person may start', () => {
    expect(statusSentence(archive([file(1, 'held'), file(2, 'held'), file(3, 'confirmed')]), 'action_needed')).toBe('The archive is not verified yet. 2 files are on hold.');
    expect(statusSentence(archive([]), 'ready')).toBe('Nothing is waiting to be archived.');
    expect(statusSentence(archive([], { can_reserve: true }), 'ready')).toBeNull();
  });
});

describe('the sections', () => {
  it('a null store and no limit draw no store block; the index and the next block follow `verified` only', () => {
    const keys = (a: Archive) => archiveSections(a, { state: 'action_needed' }).map((s) => s.key);
    expect(keys(archive([file(1, 'confirmed')]))).toEqual(['status', 'archive-index']);
    expect(keys(archive([file(1, 'confirmed')], { store: 'archive-store', limited: true, verified: true }))).toEqual(['status', 'archive-index', 'store', 'next']);
    expect(archiveSections(archive([file(1, null)], { store: 'archive-store', limited: true }), { state: 'action_needed' }).find((s) => s.key === 'store')?.items.map((i) => i.text)).toEqual(['Store: archive-store', 'Copy limit reached']);
  });
  it('a null receipt and a null job draw nothing invented: Not started, no buttons', () => {
    const f = file(1, null);
    expect(canLookup(f)).toBe(false);
    expect(canRetry(f)).toBe(false);
    expect(groupState([f])).toBe('Not started');
  });
});

describe('the start', () => {
  const sources = [{ id: 11, label: 'A' }, { id: 12, label: 'B' }, { id: 13, label: 'C' }];
  it('preselects the required sources the read also lists; nothing outside the list is chosen; none chosen is held', () => {
    const a = archive([], { sources, required_source_ids: [11, 12, 99] });
    expect(defaultSources(a)).toEqual([11, 12]);
    expect(startHeld(a, [11])).toBeNull();
    expect(startHeld(a, [])).toBe('Choose at least one source.');
    expect(startHeld(a, [99])).toBe('Choose at least one source.');
  });
});

describe('the commands', () => {
  const a = archive([file(1, 'unknown', { actions: ['lookup'] }), file(2, 'missing', { actions: ['lookup', 'retry'] }), file(3, 'held', { actions: ['lookup'] }), file(4, 'pending'), file(5, 'confirmed')], { can_reserve: true });
  const commands = archiveCommands(a, { workId: 5303, revision: 7 });
  it('describes a start and a lookup or retry only where the file may', () => {
    expect(commands.map((c) => c.id)).toEqual(['archive.reserve', 'archive.lookup.901', 'archive.lookup.902', 'archive.retry.902']);
  });
  it('the start body is the source ids and the two tokens, with no action and no key', () => {
    const c = commands[0];
    expect(c.url).toBe('/api/v1/work/5303/archive-files');
    expect(c.idempotency.field).toBeNull();
    expect(c.body({ source_ids: [11, 12] })).toEqual({ source_ids: [11, 12], expected_revision: 7, case_revision: 41 });
  });
  it('a recovery body is that row’s revision and the action, posted to that row’s job', () => {
    const lookup = commands[1];
    expect(lookup.url).toBe('/api/v1/work/5303/archive-files/901/recovery');
    expect(lookup.body({})).toEqual({ revision: 3, action: 'lookup' });
    expect(commands[3].body({})).toEqual({ revision: 3, action: 'retry' });
  });
  it('a null token is unknown: the write is disabled and the token stays null, never 0', () => {
    const none = archiveCommands({ ...a, expected_revision: null as unknown as number }, { workId: 5303, revision: 7 });
    expect(none[0].disabledReason).toMatch(/current version/);
    expect(none[0].body({ source_ids: [11] }).expected_revision).toBeNull();
    expect(archiveCommands(a, { workId: 5303, revision: null })[0].disabledReason).toMatch(/current version/);
    expect(commands[0].disabledReason).toBeUndefined();
  });
});
