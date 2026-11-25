// F-137: the contract mock's record-an-issue read and write, and the Registers tab row it adds (both project id forms).
import { beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { issueRecord, resetIssueRecord } from '../mock/issue-record.mjs';
// @ts-expect-error plain ESM module without type declarations
import { projectTab } from '../mock/project-tabs.mjs';
// @ts-expect-error plain ESM module without type declarations
import { normaliseProjectPath } from '../mock/projects.mjs';

const UUID = '00000000-0000-4000-8000-000000000101';
const body = { case_revision: 7, reference: 'ISS-0400', title: 'New one', kind: 'defect', owner_id: 4, next_action: 'Look', evidence_id: 7901, note: 'n', severity: null, external_links: [] };
const call = (method: string, id: string, raw = '', cookies = {}) => issueRecord({ method, url: new URL(normaliseProjectPath(`/api/v1/projects/${id}/issues`), 'http://m'), raw, persona: 'pm', cookies, canSee: () => true });
const tab = (id: string) => projectTab({ url: new URL(normaliseProjectPath(`/api/v1/projects/${id}/registers`), 'http://m'), persona: 'pm' });

beforeEach(() => resetIssueRecord());

describe('mock record an issue', () => {
  it('answers the read with owners and proofs, and a recorded issue shows in the read and the tab under either id form', () => {
    expect(call('get', 'P-0101').body).toMatchObject({ case_revision: 7, issues: [], owners: [{ id: 4 }, { id: 5 }, { id: 6 }], proofs: [{ id: 7901 }, { id: 7902 }] });
    const created = call('post', UUID, JSON.stringify(body));
    expect(created.status).toBe(201);
    expect(call('get', UUID).body.issues[0]).toMatchObject({ id: created.body.issue_id, reference: 'ISS-0400', status: 'Open' });
    const issues = tab(UUID).body.sections.find((s: { key: string }) => s.key === 'issues');
    expect(issues.items[0]).toMatchObject({ title: 'ISS-0400', detail: 'New one', record_id: created.body.issue_id });
    expect(issues.total).toBe(4);
  });
  it('refuses a stale revision, an unlisted owner or evidence, an over-long title and a bad severity', () => {
    expect(call('post', 'P-0101', JSON.stringify({ ...body, case_revision: 3 })).status).toBe(409);
    expect(call('post', 'P-0101', JSON.stringify({ ...body, owner_id: 99 })).status).toBe(422);
    expect(call('post', 'P-0101', JSON.stringify({ ...body, evidence_id: 1 })).status).toBe(422);
    expect(call('post', 'P-0101', JSON.stringify({ ...body, title: 'x'.repeat(241) })).status).toBe(422);
    expect(call('post', 'P-0101', JSON.stringify({ ...body, severity: 'Urgent' })).status).toBe(422);
  });
});
