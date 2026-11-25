import { describe, expect, it } from 'vitest';

import { billingParam, clientPath, countLine, directoryQuery, groupBilling, isCaseId, projectBilling, projectName, searchParam, unknownProjectsText } from '@/features/clients/labels';

const group = (contacts_needed: number, project_count = 3) => ({ key: 'a'.repeat(64), label: 'Acme', project_count, contacts_needed, api_url: '/x' });
const project = (billing: 'recorded' | 'needed' | 'unknown', client: string | null = 'Kora') => ({ case_id: '0b6f9e1a-3c44-4d0a-9d52-000000000101', title: 'Portal', client, billing });

describe('billing words', () => {
  it('a group needing two contacts says so, one is singular, none is neutral', () => {
    expect(groupBilling(group(2))).toMatchObject({ needed: true, text: '2 projects need a billing contact', tag: 'Billing contact missing' });
    expect(groupBilling(group(1)).text).toBe('1 project needs a billing contact');
    expect(groupBilling(group(0))).toMatchObject({ needed: false, text: 'None needed', tag: 'None needed' });
  });

  it('unknown is Unknown, never Set or Missing', () => {
    expect(projectBilling('recorded')).toMatchObject({ text: 'Set', tag: 'Set' });
    expect(projectBilling('needed')).toMatchObject({ text: 'Missing · invoices can’t start', tag: 'Billing contact missing' });
    const unknown = projectBilling('unknown');
    expect(unknown).toMatchObject({ text: 'Unknown', tag: 'Unknown' });
    expect(JSON.stringify(unknown)).not.toMatch(/Set|Missing|missing/);
  });

  it('a project row is named for its client, else its title', () => {
    expect(projectName(project('needed'))).toBe('Kora');
    expect(projectName(project('needed', null))).toBe('Portal');
  });

  it('owed projects count is plural-aware', () => {
    expect(unknownProjectsText(1)).toBe('1 project with an amount not known');
    expect(unknownProjectsText(2)).toBe('2 projects with an amount not known');
  });
});

describe('the count line', () => {
  const at = '2026-11-14T09:00:00Z';
  it('says loaded, and counts missing contacts only on the last page', () => {
    expect(countLine([group(2)], [project('needed'), project('unknown')], false, at)).toBe('3 clients loaded as of 14 Nov, 10:00');
    expect(countLine([group(2)], [project('needed'), project('unknown')], true, at)).toBe('3 clients loaded as of 14 Nov, 10:00 · 3 missing billing contact');
    expect(countLine([group(0)], [project('recorded')], true, at)).toBe('2 clients loaded as of 14 Nov, 10:00');
  });
});

describe('the address', () => {
  it('sends billing only for the three known values', () => {
    expect(billingParam('needed')).toBe('needed');
    expect(billingParam('recorded')).toBe('recorded');
    expect(billingParam('unknown')).toBe('unknown');
    for (const bad of ['bogus', 'NEEDED', '', ' needed', null, undefined]) expect(billingParam(bad)).toBeUndefined();
  });

  it('trims q, caps it at 100 characters and drops a blank one', () => {
    expect(searchParam('  acme ')).toBe('acme');
    expect(searchParam('x'.repeat(150))).toHaveLength(100);
    expect(searchParam('   ')).toBeUndefined();
    expect(directoryQuery('kora', 'bogus')).toEqual({ q: 'kora', billing: undefined });
  });

  it('a UUID is a workspace and anything else a group key', () => {
    expect(isCaseId('0b6f9e1a-3c44-4d0a-9d52-5f7a1c2e8b10')).toBe(true);
    for (const key of ['a'.repeat(64), 'CL-3501', 'P-0101', '', '0b6f9e1a-3c44-4d0a-9d52-5f7a1c2e8b1']) expect(isCaseId(key)).toBe(false);
  });

  it('encodes a route id once', () => {
    expect(clientPath('a/b%c')).toBe('/clients/a%2Fb%25c');
  });
});
