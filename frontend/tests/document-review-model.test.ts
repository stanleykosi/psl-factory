import { describe, expect, it } from 'vitest';

import { documentHref, isDocument, isVersionId, noteProblem, paragraphsOf, publicationOf, reviewHrefOf, verdictsOf, type LiveDocument } from '@/features/documents/documentModel';

const doc = (patch: Record<string, unknown> = {}) => ({ title: 'SOW', version: 2, revision: 7, audience: 'Client', current: true, decisions: ['approve', 'return'], django_url: '/x', preview: [{ field: 'Scope', text: 'x' }], ...patch });

describe('isDocument', () => {
  it('accepts the live preview and refuses a body that is not one', () => {
    expect(isDocument(doc())).toBe(true);
    expect(isDocument(doc({ preview: [] }))).toBe(true);
    for (const bad of [null, [], 'x', {}, doc({ title: 1 }), doc({ version: '2' }), doc({ revision: 1.5 }), doc({ audience: null }), doc({ current: 'yes' }), doc({ decisions: 'approve' }), doc({ preview: [{ field: 'a' }] }), doc({ preview: null })]) {
      expect(isDocument(bad)).toBe(false);
    }
  });
});

describe('publicationOf', () => {
  it('reads the status word and the findings, and nothing else', () => {
    expect(publicationOf({ review_status: 'Approved', findings: ['a', ' ', 3], editable: [] })).toEqual({ review_status: 'Approved', findings: ['a'] });
    expect(publicationOf({ review_status: null, findings: [] })).toEqual({ review_status: null, findings: [] });
    for (const bad of [null, {}, { findings: 'a' }, { review_status: 3, findings: [] }]) expect(publicationOf(bad)).toBeNull();
  });
});

describe('isVersionId', () => {
  it('takes only a whole positive 64-bit number written plainly', () => {
    for (const ok of ['1', '2901', '9223372036854775807', '1000000000000000000']) expect(isVersionId(ok), ok).toBe(true);
    for (const bad of ['', 'abc', '0', '00', '02', '2.5', '-1', '+1', ' 1', '1 ', '1e3', '0x10', '２９０１', '9223372036854775808', '12345678901234567890', '1/2', '1?v=2', '1#x', '../1', '%31', 'latest']) expect(isVersionId(bad), bad).toBe(false);
  });
});

describe('verdictsOf', () => {
  it('keeps only approve and return, in that order, never reject', () => {
    expect(verdictsOf(doc({ decisions: ['return', 'reject', 'approve'] }) as LiveDocument)).toEqual(['approve', 'return']);
    expect(verdictsOf(doc({ decisions: ['reject'] }) as LiveDocument)).toEqual([]);
    expect(verdictsOf(doc({ decisions: [] }) as LiveDocument)).toEqual([]);
  });
});

describe('noteProblem', () => {
  it('is one rule for every verdict: 1 to 4000 characters, not blank', () => {
    expect(noteProblem('')).toBe('Add a note to record your decision.');
    expect(noteProblem(' \n\t')).toBe('Add a note to record your decision.');
    expect(noteProblem('x'.repeat(4001))).toBe('Keep the note to 4000 characters or fewer.');
    expect(noteProblem('x')).toBeNull();
    expect(noteProblem('x'.repeat(4000))).toBeNull();
  });
});

describe('paragraphsOf', () => {
  it('splits on blank lines and leaves markup as characters', () => {
    expect(paragraphsOf('a <b>x</b>\n\n  b  \n \nc')).toEqual(['a <b>x</b>', 'b', 'c']);
    expect(paragraphsOf('')).toEqual([]);
  });
});

describe('the Documents-tab link', () => {
  const CASE = '00000000-0000-4000-8000-000000000101';
  it('documentHref is the page of one version id', () => {
    expect(documentHref(CASE, 2901)).toBe(`/projects/${CASE}/documents/2901`);
    expect(documentHref('a b', '5')).toBe('/projects/a%20b/documents/5');
  });

  it('a row links only when its api_url is exactly this project’s document-review path', () => {
    expect(reviewHrefOf(CASE, `/api/v1/projects/${CASE}/document-reviews/2901`)).toBe(`/projects/${CASE}/documents/2901`);
    const refused: unknown[] = [
      undefined,
      null,
      42,
      '',
      `/api/v1/projects/${CASE.replace('101', '102')}/document-reviews/2901`,
      `/api/v1/projects/${CASE}/document-reviews/`,
      `/api/v1/projects/${CASE}/document-reviews/abc`,
      `/api/v1/projects/${CASE}/document-reviews/02`,
      `/api/v1/projects/${CASE}/document-reviews/2901/publication`,
      `/api/v1/projects/${CASE}/document-reviews/2901?x=1`,
      `/api/v1/projects/${CASE}/document-reviews/2901#x`,
      `/api/v1/projects/${CASE}/documents/2901`,
      `/api/v1/projects/${CASE}/../x/document-reviews/2901`,
      `/API/v1/projects/${CASE}/document-reviews/2901`,
      ` /api/v1/projects/${CASE}/document-reviews/2901`,
      `//evil.example/api/v1/projects/${CASE}/document-reviews/2901`,
      `https://evil.example/api/v1/projects/${CASE}/document-reviews/2901`,
      `javascript:alert(1)//api/v1/projects/${CASE}/document-reviews/2901`,
      `/api/v1/projects/%2e%2e/document-reviews/2901`,
    ];
    for (const value of refused) expect(reviewHrefOf(CASE, value), String(value)).toBeUndefined();
  });
});
