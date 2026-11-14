import { describe, expect, it } from 'vitest';

import {
  buildIntake,
  caseOptionUnusable,
  dependentsOf,
  newIdempotencyKey,
  parentValue,
  resolveCase,
  shownFields,
  startableHere,
} from '@/features/start-work/intake';
import type { Field, Line } from '@/features/start-work/types';

const f = (name: string, type: string, extra: Partial<Field> = {}): Field => ({ name, label: name, type, required: false, ...extra });

const KINDS: Field[] = [
  f('text', 'text'),
  f('long_text', 'long_text'),
  f('date', 'date'),
  f('date_range', 'date_range'),
  f('period', 'period'),
  f('datetime', 'datetime'),
  f('integer', 'integer'),
  f('choice', 'choice', { options: [{ value: 'a', label: 'A' }, { value: 'b', label: 'B' }] }),
  f('record', 'record', { options_source: 'line_options' }),
  f('records', 'records', { options_source: 'line_options', multiple: true }),
  f('display', 'display', { value: 'Shown only' }),
];

describe('buildIntake: the submitted shape per kind (D-START-INTAKE)', () => {
  it('sends each kind in its shape and leaves out the display field', () => {
    const local = '2026-11-17T09:30';
    const intake = buildIntake(KINDS, {
      text: '  Hello  ',
      long_text: 'Line one\nLine two',
      date: '2026-11-17',
      date_range: { from: '2026-11-09', to: '2026-11-13' },
      period: '2026-11',
      datetime: local,
      integer: '3',
      choice: 'b',
      record: { value: 'P-0101', label: 'Lagoon' },
      records: [
        { value: 'ISS-1', label: 'One' },
        { value: 'ISS-2', label: 'Two' },
      ],
      display: 'ignored',
    });
    expect(intake).toEqual({
      text: 'Hello',
      long_text: 'Line one\nLine two',
      date: '2026-11-17',
      date_range: { from: '2026-11-09', to: '2026-11-13' },
      period: '2026-11',
      datetime: new Date(local).toISOString(),
      integer: 3,
      choice: 'b',
      record: 'P-0101',
      records: ['ISS-1', 'ISS-2'],
    });
    expect(intake.datetime).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
    expect(typeof intake.integer).toBe('number');
    expect(intake).not.toHaveProperty('display');
  });

  it('leaves out blank and unparseable values; a half-filled range sends the filled part', () => {
    const intake = buildIntake(KINDS, {
      text: '   ',
      long_text: '',
      date: '',
      date_range: { from: '', to: '2026-11-13' },
      period: '',
      datetime: 'not a time',
      integer: '2.5',
      choice: '',
      records: [],
    });
    expect(intake).toEqual({ date_range: { to: '2026-11-13' } });
    expect(buildIntake(KINDS, { date_range: { from: '', to: '' }, integer: 'abc' })).toEqual({});
    expect(buildIntake(KINDS, {})).toEqual({});
  });

  it('never sends an evidence, money or unknown field', () => {
    const fields = [f('proof', 'evidence'), f('amount', 'money'), f('odd', 'colour'), f('note', 'text')];
    expect(buildIntake(fields, { proof: 'EV-1', amount: '100', odd: 'red', note: 'kept' })).toEqual({ note: 'kept' });
  });
});

const project: Field = f('project', 'record', { required: true, options_source: 'line_options' });
const milestone: Field = f('milestone', 'record', { required: true, options_source: 'line_options', depends_on: 'project' });
const proof: Field = f('proof', 'record', { options_source: 'line_options', depends_on: 'milestone' });
const projectLine: Line = { key: 'invoice', title: 'Invoice', group: 'g', case_scope: 'project', case_field: 'project', intake: [project, milestone, proof] };
const fixedLine: Line = { key: 'leadership_report', title: 'Leadership report', group: 'g', case_scope: 'fixed', case_id: 'C-PMO-REPORTING', case_revision: 4, intake: [] };

describe('resolveCase: the case comes from the chosen option or the fixed line, never guessed', () => {
  it('project scope takes case_id and case_revision from the option chosen in case_field', () => {
    const values = { project: { value: 'P-0101', label: 'Lagoon', case_id: 'C-0101', case_revision: 6 } };
    expect(resolveCase(projectLine, values)).toEqual({ case_id: 'C-0101', case_revision: 6 });
    expect(caseOptionUnusable(projectLine, values)).toBe(false);
  });

  it('no project chosen, or an option without a case, resolves to nothing', () => {
    expect(resolveCase(projectLine, {})).toBeNull();
    expect(caseOptionUnusable(projectLine, {})).toBe(false);
    const ojo = { project: { value: 'P-0126', label: 'Ojo Foods' } };
    expect(resolveCase(projectLine, ojo)).toBeNull();
    expect(caseOptionUnusable(projectLine, ojo)).toBe(true);
    expect(resolveCase(projectLine, { project: { value: 'P-1', label: 'x', case_id: 'C-1' } })).toBeNull();
  });

  it('fixed scope takes the line case, whatever is chosen', () => {
    expect(resolveCase(fixedLine, { project: { value: 'P-0101', label: 'x', case_id: 'C-0101', case_revision: 6 } })).toEqual({
      case_id: 'C-PMO-REPORTING',
      case_revision: 4,
    });
  });

  it('no case_scope, or a fixed line without a case, resolves to nothing and cannot start here', () => {
    const { case_scope: _omit, ...unscoped } = projectLine;
    void _omit;
    expect(resolveCase(unscoped, { project: { value: 'P-0101', label: 'x', case_id: 'C-0101', case_revision: 6 } })).toBeNull();
    expect(startableHere(unscoped)).toBe(false);
    const noCase = { ...fixedLine, case_id: undefined };
    expect(resolveCase(noCase, {})).toBeNull();
    expect(startableHere(noCase)).toBe(false);
  });
});

describe('fields this release renders', () => {
  it('drops optional evidence, money and unknown kinds, keeping the order returned', () => {
    const line = { ...projectLine, intake: [project, f('proof', 'evidence'), milestone, f('fee', 'money'), f('x', 'colour')] };
    expect(shownFields(line).map((field) => field.name)).toEqual(['project', 'milestone']);
    expect(startableHere(line)).toBe(true);
  });

  it('a required evidence field, or another start route, means the line cannot start here', () => {
    expect(startableHere({ ...projectLine, intake: [project, f('proof', 'evidence', { required: true })] })).toBe(false);
    expect(startableHere({ ...projectLine, start_via: 'finance_import' })).toBe(false);
    expect(startableHere({ ...projectLine, start_via: 'work_start' })).toBe(true);
    expect(startableHere(fixedLine)).toBe(true);
  });
});

describe('parents and dependents', () => {
  it('a parent clears every field that depends on it, transitively', () => {
    expect(dependentsOf(projectLine.intake, 'project')).toEqual(['milestone', 'proof']);
    expect(dependentsOf(projectLine.intake, 'milestone')).toEqual(['proof']);
    expect(dependentsOf(projectLine.intake, 'proof')).toEqual([]);
  });

  it('the parent sent to E-LINE-OPTIONS is the chosen option value', () => {
    expect(parentValue(milestone, { project: { value: 'P-0101', label: 'Lagoon' } })).toBe('P-0101');
    expect(parentValue(milestone, {})).toBeUndefined();
    expect(parentValue(project, { project: { value: 'P-0101', label: 'Lagoon' } })).toBeUndefined();
  });
});

it('idempotency keys are fresh UUIDs', () => {
  const a = newIdempotencyKey();
  expect(a).toMatch(/^[0-9a-f-]{36}$/);
  expect(newIdempotencyKey()).not.toBe(a);
});
