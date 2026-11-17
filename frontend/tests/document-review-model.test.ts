// F-29: the document review model. The check words, the note rule, the version rule and the plain-text paragraphs.
import { describe, expect, it } from 'vitest';

import {
  amountsTag,
  checkStatus,
  checksOf,
  checkTag,
  checkTone,
  draftedByText,
  firstFlag,
  isDocument,
  noteProblem,
  paragraphsOf,
  parseVersion,
  returnedByText,
  sectionsOf,
  type DocumentView,
} from '@/features/documents/documentModel';

const base = { document_id: 'D-1', version: '2', title: 'Statement of work', status: 'x', template: 't', body_url: 'https://files.example.test/a.pdf' } as DocumentView;

describe('checks: the four backend statuses and absent, never a word the backend did not send', () => {
  it.each([
    ['done', 'Matches COST-0140 v2', { text: 'Matches COST-0140 v2' }, 'done'],
    ['done', undefined, { text: 'Done' }, 'done'],
    ['held', 'Waiting for the costing', { text: 'Held', reason: 'Waiting for the costing' }, 'waiting'],
    ['blocked', 'Costing is stopped', { text: 'Blocked', reason: 'Costing is stopped' }, 'person'],
    ['unknown', 'Matches COST-0140 v2', { text: 'Unknown', reason: 'Matches COST-0140 v2' }, 'neutral'],
    [undefined, 'Matches COST-0140 v2', { text: 'Unknown', reason: 'Matches COST-0140 v2' }, 'neutral'],
    ['passed', undefined, { text: 'Unknown' }, 'neutral'],
  ])('status %s with detail %s', (status, detail, tag, tone) => {
    const check = { key: 'amounts', label: 'Amounts', status, detail };
    expect(checkTag(check)).toEqual(tag);
    expect(checkTone(check)).toBe(tone);
  });

  it('an unknown amounts check never reads Matches in the tag, and absent checks give no tag', () => {
    const unknown = { ...base, checks: [{ key: 'amounts', label: 'Amounts', status: 'unknown', detail: 'Matches COST-0140 v2' }] } as DocumentView;
    expect(amountsTag(unknown)).toEqual({ text: 'Unknown', tone: 'neutral' });
    expect(amountsTag(base)).toBeUndefined();
    expect(checkStatus({})).toBe('unknown');
  });

  it('keeps the order sent and drops entries without a key or label', () => {
    const doc = { ...base, checks: [{ key: 'b', label: 'B' }, { key: 'a' }, null, { label: 'no key' }, { key: 'c', label: 'C' }] } as unknown as DocumentView;
    expect(checksOf(doc).map((c) => c.key)).toEqual(['b', 'c']);
  });
});

describe('note rule: approve sends no note; return needs 1 to 2000 characters', () => {
  it.each([
    ['approve', '', null],
    ['approve', 'x'.repeat(2001), 'Keep the note to 2000 characters or fewer.'],
    ['return', '', 'Add a note to return it.'],
    ['return', '   \n\t', 'Add a note to return it.'],
    ['return', 'Fix section 4', null],
    ['return', 'x'.repeat(2000), null],
    ['return', 'x'.repeat(2001), 'Keep the note to 2000 characters or fewer.'],
  ] as const)('%s with %j', (verdict, note, problem) => {
    expect(noteProblem(verdict, note)).toBe(problem);
  });
});

describe('version: the latest is never guessed', () => {
  it.each([['1', '1'], ['2', '2'], ['12', '12']])('%s is read', (v, out) => expect(parseVersion(v)).toBe(out));
  it.each([[null], [undefined], [''], ['latest'], ['0'], ['02'], ['2.5'], ['-1'], ['2 '], [' 2'], ['2;3'], ['１'], ['1234567890']])('%j is not a version', (v) => expect(parseVersion(v)).toBeNull());
});

describe('plain text', () => {
  it('splits paragraphs on blank lines and keeps markup characters as text', () => {
    expect(paragraphsOf('One <b>x</b>\n\nTwo <script>alert(1)</script>\n  \n\nThree')).toEqual(['One <b>x</b>', 'Two <script>alert(1)</script>', 'Three']);
  });

  it('reads sections, the first flag and a missing sections field', () => {
    const doc = {
      ...base,
      sections: [
        { key: 'a', heading: 'A', text: 'a' },
        { key: 'b', heading: 'B', text: 'b', notes: [{ agent: 'tola', text: 'check' }] },
        { key: 'bad' },
      ],
    } as unknown as DocumentView;
    expect(sectionsOf(doc)).toHaveLength(2);
    expect(firstFlag(sectionsOf(doc)!)).toEqual({ agent: 'Tola', number: 2, text: 'check' });
    expect(sectionsOf(base)).toBeUndefined();
    expect(sectionsOf({ ...base, sections: [] })).toEqual([]);
  });
});

describe('sentences from the response only', () => {
  it('drafted by and returned by leave out what is not sent', () => {
    expect(draftedByText({ ...base, drafted_by: { agent: 'tola', from: ['the planning record', 'the approved costing'] } })).toBe('Drafted by Tola from the planning record and the approved costing.');
    expect(draftedByText({ ...base, drafted_by: { agent: 'tola', from: ['a', 'b', 'c'] } })).toBe('Drafted by Tola from a, b and c.');
    expect(draftedByText({ ...base, drafted_by: { agent: 'tola' } })).toBe('Drafted by Tola.');
    expect(draftedByText(base)).toBeUndefined();
    expect(returnedByText({ by: 'Kemi Adebayo', role: 'PMO Lead' })).toBe('Returned by Kemi Adebayo (PMO Lead)');
    expect(returnedByText({ role: 'PMO Lead' })).toBe('Returned by PMO Lead');
    expect(returnedByText({})).toBe('Returned');
  });

  it('a body without a document id, title and version is not a document', () => {
    expect(isDocument(base)).toBe(true);
    expect(isDocument({ title: 'x' })).toBe(false);
    expect(isDocument(null)).toBe(false);
    expect(isDocument([])).toBe(false);
  });
});
