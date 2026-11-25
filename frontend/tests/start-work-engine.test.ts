// F-92: the form engine on the served `request_schema` of the five PMO lines: the controls, the body (validated against that schema with
// ajv), the 422 map, the minutes parts and the weekly guard. The schemas are the mock's, built as the backend builds them.
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import { describe, expect, it } from 'vitest';

import { jsonBody, missingOf, targetOf } from '@/features/start-work/engine/body';
import { minutesParts } from '@/features/start-work/engine/minutes';
import { planOf } from '@/features/start-work/engine/plan';
import { leavesOf } from '@/features/start-work/engine/schema';
import { requestLabel } from '@/features/start-work/engine/escalations';
import { isStartable } from '@/features/start-work/LineChooser';
import { pmoChange } from '@/features/start-work/lines/pmoChange';
import { pmoEmergency } from '@/features/start-work/lines/pmoEmergency';
import { pmoEscalation } from '@/features/start-work/lines/pmoEscalation';
import { pmoIssues } from '@/features/start-work/lines/pmoIssues';
import { pmoMinutes } from '@/features/start-work/lines/pmoMinutes';
import { localMidnight, weeklyReport } from '@/features/start-work/lines/weeklyReport';
import type { Values } from '@/features/start-work/intake';
import type { Line } from '@/features/start-work/types';

// @ts-expect-error plain ESM module without type declarations
import { SCHEMAS, startLive } from '../mock/start-live.mjs';

const ajv = addFormats(new Ajv({ allErrors: true, strict: false }));
const CTX = { caseId: '00000000-0000-4000-8000-000000000001', caseRevision: 4, idempotencyKey: 'key-1' };
const pick = (id: number) => ({ value: String(id), label: `Row ${id}` });
const servedLines = (startLive({ method: 'get', url: new URL('http://m/api/v1/lines'), persona: 'pm' })[1] as { items: Line[] }).items;
const served = (key: string) => servedLines.find((l) => l.key === key) as Line;

const FORMS = { 'pmo-issues/v1': pmoIssues, 'pmo-escalation/v1': pmoEscalation, 'pmo-emergency/v1': pmoEmergency, 'pmo-change/v1': pmoChange };
const VALUES: Record<string, Values> = {
  'pmo-issues/v1': { issue_id: pick(12) },
  'pmo-escalation/v1': { request_id: pick(23), reference: ' Escalate it ' },
  'pmo-emergency/v1': { profile_id: pick(32), 'inputs.authorization_id': pick(42), 'inputs.audience': 'client', reference: 'Fire' },
  'pmo-change/v1': { version_id: pick(72), reference: 'Change' },
};
const EXPECTED: Record<string, unknown> = {
  'pmo-issues/v1': { issue_id: 12 },
  'pmo-escalation/v1': { request_id: 23, template_id: null },
  'pmo-emergency/v1': { profile_id: 32, inputs: { template_id: null, authorization_id: 42, outcome_id: null, audience: 'client' } },
  'pmo-change/v1': { version_id: 72, inputs: { template_id: null, authorization_id: null } },
};

describe('fieldsOf: the served schema to controls (AC1)', () => {
  const names = (key: string, config: Parameters<typeof planOf>[0]) => {
    const plan = planOf(config, served(key).request_schema);
    return plan === 'unsupported' ? plan : plan.fields.map((f) => [f.name, f.kind, f.required]);
  };

  it('issues: one required record, and no reference (the server derives it)', () => {
    const plan = planOf({ key: 'x', drawerTitle: '', startLabel: '', labels: { issue_id: { label: 'Issue' } }, sources: { issue_id: { kind: 'sources', field: 'issue_id' } }, needs: ['issue_id'] }, SCHEMAS['pmo-issues/v1']);
    expect(plan).not.toBe('unsupported');
    if (plan === 'unsupported') return;
    expect(plan.fields.map((f) => [f.name, f.kind, f.required])).toEqual([['issue_id', 'record', true]]);
    expect(plan.reference).toBeNull();
  });

  it('escalation: request required, template optional (null), reference 1..160', () => {
    expect(isStartable(served('pmo-escalation/v1'))).toBe(true);
    const form = pmoEscalation;
    expect(form.missing({}, served('pmo-escalation/v1'))).toEqual([{ name: 'request_id', label: 'Escalation request' }, { name: 'reference', label: 'Reference' }]);
  });

  it('emergency: record required; authorisation, outcome, template and audience optional; audience values come from the schema', () => {
    const line = served('pmo-emergency/v1');
    expect(pmoEmergency.missing({}, line)).toEqual([{ name: 'profile_id', label: 'Emergency record' }, { name: 'reference', label: 'Reference' }]);
    expect(leavesOf(line.request_schema)).toContainEqual({ path: 'inputs.audience', kind: 'choice', nullable: true, optional: false, values: ['internal', 'client'] });
  });

  it('change: version required; authorisation and template optional', () => {
    expect(pmoChange.missing({}, served('pmo-change/v1'))).toEqual([{ name: 'version_id', label: 'Change version' }, { name: 'reference', label: 'Reference' }]);
  });

  it('minutes: template, audience, notes file and reference required; meeting optional', () => {
    expect(pmoMinutes.missing({}, served('pmo-minutes/v1')).map((m) => m.name)).toEqual(['template_id', 'audience', 'notes_file', 'reference']);
  });

  it('the leadership schema (array and object leaves) is unsupported, and its row is not startable', () => {
    expect(leavesOf(served('pmo-leadership-report/v1').request_schema)).toBe('unsupported');
    expect(isStartable(served('pmo-leadership-report/v1'))).toBe(false);
  });

  it('a required id the config has no source for makes the line unsupported, never a partial form', () => {
    const config = { key: 'x', drawerTitle: '', startLabel: '', labels: { issue_id: { label: 'Issue' } }, sources: {}, needs: [] };
    expect(planOf(config, SCHEMAS['pmo-issues/v1'])).toBe('unsupported');
    // a leaf the config has no words for
    expect(planOf({ ...config, sources: { issue_id: { kind: 'sources' as const, field: 'issue_id' } }, labels: {} }, SCHEMAS['pmo-issues/v1'])).toBe('unsupported');
    expect(names('pmo-issues/v1', config)).toBe('unsupported');
  });

  it('an array, a boolean or a non-string enum anywhere is unsupported', () => {
    const wrap = (leaf: unknown) => ({ properties: { intake: { type: 'object', properties: { a: leaf }, required: ['a'] } } });
    expect(leavesOf(wrap({ type: 'array', items: { type: 'integer' } }))).toBe('unsupported');
    expect(leavesOf(wrap({ type: 'boolean' }))).toBe('unsupported');
    expect(leavesOf(wrap({ enum: [1, 2] }))).toBe('unsupported');
    expect(leavesOf(wrap({ anyOf: [{ type: 'array' }, { type: 'null' }] }))).toBe('unsupported');
    expect(leavesOf({})).toBe('unsupported');
  });
});

describe('buildBody: exactly the schema keys, valid against the served schema (AC2)', () => {
  for (const [key, form] of Object.entries(FORMS)) {
    it(`${key}: the body validates, has only the schema's keys, no background, and nulls for empty optionals`, () => {
      const line = served(key);
      const body = form.buildBody(VALUES[key], CTX, line) as Record<string, unknown>;
      const validate = ajv.compile(line.request_schema as object);
      expect(validate(body), JSON.stringify(validate.errors)).toBe(true);
      expect(body.intake).toEqual(EXPECTED[key]);
      expect('background' in body).toBe(false);
      expect(Object.keys(body).sort()).toEqual(Object.keys(((line.request_schema as unknown) as { properties: object }).properties).filter((k) => k !== 'background').sort());
      expect(body.line).toBe(key);
      expect(body.case_revision).toBe(4);
      expect(body.idempotency_key).toBe('key-1');
      if (key === 'pmo-issues/v1') expect('reference' in body).toBe(false);
      else expect(typeof body.reference).toBe('string');
    });

    it(`${key}: one extra key fails the same schema`, () => {
      const line = served(key);
      const body = { ...(form.buildBody(VALUES[key], CTX, line) as object), extra: 1 };
      expect(ajv.compile(line.request_schema as object)(body)).toBe(false);
    });
  }

  it('trims the reference and sends the integer ids, not the labels', () => {
    const body = pmoEscalation.buildBody(VALUES['pmo-escalation/v1'], CTX, served('pmo-escalation/v1')) as { reference: string; intake: { request_id: unknown } };
    expect(body.reference).toBe('Escalate it');
    expect(body.intake.request_id).toBe(23);
  });

  it('a body is never built for a schema the engine cannot draw', () => {
    expect(() => pmoIssues.buildBody({}, CTX, served('pmo-leadership-report/v1'))).toThrow();
    expect(() => pmoIssues.buildBody({}, CTX, undefined)).toThrow();
  });
});

describe('the weekly guard (AC3)', () => {
  it('the hand-built weekly body validates against the served weekly schema', () => {
    const line = served('pmo-weekly-report/v1');
    const body = weeklyReport.buildBody({ week: { from: '2026-11-16', to: '2026-11-22' }, reference: 'Week 47' }, CTX, line);
    const validate = ajv.compile(line.request_schema as object);
    expect(validate(body), JSON.stringify(validate.errors)).toBe(true);
    expect(localMidnight('2026-11-16')).toMatch(/^2026-11-16T00:00:00[+-]\d\d:\d\d$/);
  });
});

describe('the 422 map (AC9)', () => {
  const plan = (key: string, line = key) =>
    planOf(
      key === 'pmo-emergency/v1'
        ? { key, drawerTitle: '', startLabel: '', labels: { profile_id: { label: 'Emergency record' }, 'inputs.authorization_id': { label: 'Authorisation' }, 'inputs.outcome_id': { label: 'Outcome' }, 'inputs.template_id': { label: 'Template' }, 'inputs.audience': { label: 'Audience' } }, sources: { profile_id: { kind: 'sources', field: 'profile_id' }, 'inputs.authorization_id': { kind: 'sources', field: 'x' }, 'inputs.outcome_id': { kind: 'sources', field: 'y' }, 'inputs.template_id': { kind: 'sources', field: 'z' } }, needs: [] }
        : { key, drawerTitle: '', startLabel: '', strip: 'data.', skip: ['data.protocol', 'data.evidence_id', 'data.publish'], labels: { template_id: { label: 'Template' }, meeting_version_id: { label: 'Meeting' }, audience: { label: 'Audience' } }, sources: { template_id: { kind: 'sources', field: 'a' }, meeting_version_id: { kind: 'sources', field: 'b' } }, needs: [], upload: { name: 'notes_file', label: 'Notes file' } },
      SCHEMAS[line],
    );
  const emergency = plan('pmo-emergency/v1') as Exclude<ReturnType<typeof planOf>, 'unsupported'>;
  const minutes = plan('pmo-minutes/v1') as Exclude<ReturnType<typeof planOf>, 'unsupported'>;

  it.each([
    ['case_id', 'project'],
    ['case_revision', 'project'],
    ['line', 'general'],
    ['idempotency_key', 'general'],
    ['reference', 'reference'],
    ['intake.profile_id', 'profile_id'],
    ['profile_id', 'profile_id'],
    ['intake.inputs.authorization_id', 'inputs.authorization_id'],
    ['inputs.authorization_id', 'inputs.authorization_id'],
    ['authorization_id', undefined],
    ['intake.inputs.audience', 'inputs.audience'],
    ['intake.inputs', 'inputs.authorization_id'],
    ['inputs', 'inputs.authorization_id'],
    ['intake.inputs.unknown', undefined],
    ['background', undefined],
  ])('emergency: %s goes to %s', (name, control) => {
    expect(targetOf(emergency, name)).toBe(control);
  });

  it.each([
    ['template_id', 'template_id'],
    ['audience', 'audience'],
    ['notes_file', 'notes_file'],
    ['reference', 'reference'],
    ['meeting_version_id', 'meeting_version_id'],
    ['case_revision', 'project'],
    ['idempotency_key', 'general'],
    ['data.template_id', 'template_id'],
    ['publish', undefined],
  ])('minutes: %s goes to %s', (name, control) => {
    expect(targetOf(minutes, name)).toBe(control);
  });

  it('a line with no reference sends a `reference` problem to its own box', () => {
    const issues = planOf({ key: 'x', drawerTitle: '', startLabel: '', labels: { issue_id: { label: 'Issue' } }, sources: { issue_id: { kind: 'sources', field: 'issue_id' } }, needs: [] }, SCHEMAS['pmo-issues/v1']);
    expect(issues).not.toBe('unsupported');
    if (issues !== 'unsupported') expect(targetOf(issues, 'reference')).toBeUndefined();
  });
});

describe('minutes parts (AC7)', () => {
  const line = served('pmo-minutes/v1');
  const file = new File(['notes'], 'notes.txt', { type: 'text/plain' });

  it('sends case_revision, idempotency_key, reference, template_id, audience and notes_file; the meeting only when chosen; never background', () => {
    const without = pmoMinutes.buildBody({ template_id: pick(54), audience: 'internal', notes_file: file, reference: ' Minutes ' }, CTX, line) as { caseId: string; form: FormData };
    expect([...without.form.keys()].sort()).toEqual(['audience', 'case_revision', 'idempotency_key', 'notes_file', 'reference', 'template_id']);
    expect(without.form.get('reference')).toBe('Minutes');
    expect(without.form.get('template_id')).toBe('54');
    expect(without.form.get('case_revision')).toBe('4');
    const withMeeting = pmoMinutes.buildBody({ template_id: pick(54), meeting_version_id: pick(91), audience: 'client', notes_file: file, reference: 'm' }, CTX, line) as { form: FormData };
    expect(withMeeting.form.get('meeting_version_id')).toBe('91');
    expect(withMeeting.form.has('background')).toBe(false);
  });

  it('minutesParts reads the same plan the form draws', () => {
    const plan = planOf({ key: 'm', drawerTitle: '', startLabel: '', strip: 'data.', skip: ['data.protocol', 'data.evidence_id', 'data.publish'], labels: { template_id: { label: 'T' }, meeting_version_id: { label: 'M' }, audience: { label: 'A' } }, sources: { template_id: { kind: 'sources', field: 'a' }, meeting_version_id: { kind: 'sources', field: 'b' } }, needs: [], upload: { name: 'notes_file', label: 'N' } }, line.request_schema);
    expect(plan).not.toBe('unsupported');
    if (plan === 'unsupported') return;
    expect(missingOf(plan, {}).map((m) => m.name)).toEqual(['template_id', 'audience', 'notes_file', 'reference']);
    expect([...minutesParts(plan, { template_id: pick(1), audience: 'internal', notes_file: file, reference: 'r' }, CTX).form.keys()]).toContain('notes_file');
  });
});

describe('labels', () => {
  it('words a register request from the served direction and target', () => {
    expect(requestLabel({ id: 23, direction: 'escalate', target: 'PMO' })).toBe('Escalate to PMO · #23');
    expect(requestLabel({ id: 22, direction: 'de_escalate', target: 'Client' })).toBe('De-escalate to Client · #22');
  });

  it('jsonBody is the only builder of POST /work bodies', () => {
    const plan = planOf({ key: 'x', drawerTitle: '', startLabel: '', labels: { issue_id: { label: 'Issue' } }, sources: { issue_id: { kind: 'sources', field: 'issue_id' } }, needs: [] }, SCHEMAS['pmo-issues/v1']);
    if (plan === 'unsupported') throw new Error('unsupported');
    expect(jsonBody('pmo-issues/v1', plan, { issue_id: pick(3) }, CTX).intake).toEqual({ issue_id: 3 });
  });
});
