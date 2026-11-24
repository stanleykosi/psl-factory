import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { issuesRoute } from '../mock/issues.mjs';

// F-111: the work item and the three issue reads the mock serves, for every fixture, against the live contract.
type Responses = Record<string, { content: { 'application/json': { schema: object } } }>;
const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as { paths: Record<string, Record<string, { responses: Responses }>> };
const ajv = new Ajv2020({ allErrors: true, strict: true, allowUnionTypes: true });
addFormats(ajv);
const schemaOf = (path: string) => ajv.compile(contract.paths[path].get.responses['200'].content['application/json'].schema);
const validWork = schemaOf('/api/v1/work/{work_id}');
const validFollowup = schemaOf('/api/v1/work/{work_id}/issue-followup');
const validDetail = schemaOf('/api/v1/projects/{case_id}/issues/{issue_id}');
const validMessages = schemaOf('/api/v1/projects/{case_id}/issues/{issue_id}/messages');

const get = (path: string, scenario?: string) => issuesRoute({ method: 'get', url: new URL(path, 'http://m.local'), scenario, persona: 'pmo_lead' }) as [number, Record<string, unknown>];
const CASE = '6c2f1d3e-1a4b-4b8e-9d0a-0a1b2c3d4e5f';

describe('the issue fixtures are the live shape', () => {
  it.each([5101, 5102, 5103, 5104, 5105, 5107])('work %i: the work item and the follow-up validate', (id) => {
    const [workStatus, work] = get(`/api/v1/work/${id}`);
    expect(workStatus).toBe(200);
    expect(validWork(work), ajv.errorsText(validWork.errors)).toBe(true);
    const [status, followup] = get(`/api/v1/work/${id}/issue-followup`);
    expect(status).toBe(200);
    expect(validFollowup(followup), ajv.errorsText(validFollowup.errors)).toBe(true);
  });

  it.each([233, 234, 235, 236, 237, 239])('issue %i: the detail and the messages validate unless the fixture answers an error', (issue) => {
    const [dStatus, detail] = get(`/api/v1/projects/${CASE}/issues/${issue}`);
    if (dStatus === 200) expect(validDetail(detail), ajv.errorsText(validDetail.errors)).toBe(true);
    else expect(dStatus).toBe(503);
    const [mStatus, messages] = get(`/api/v1/projects/${CASE}/issues/${issue}/messages`);
    if (mStatus === 200) expect(validMessages(messages), ajv.errorsText(validMessages.errors)).toBe(true);
    else expect(mStatus).toBe(403);
  });
});
