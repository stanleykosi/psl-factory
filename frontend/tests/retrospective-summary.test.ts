import { describe, expect, it } from 'vitest';

import { hasHeadingLine, parseSummary, SUMMARY_LIMIT, writeSummary, type Boxes } from '@/features/retrospective/summary';

const boxes = (b: Partial<Boxes>): Boxes => ({ well: '', didnt: '', lessons: '', ...b });

describe('writeSummary', () => {
  it('writes one box under its heading', () => {
    expect(writeSummary(boxes({ well: 'UAT finished on time.' }))).toBe('## What went well\nUAT finished on time.');
  });
  it('writes all three in order, one blank line apart', () => {
    expect(writeSummary(boxes({ lessons: 'C', well: 'A', didnt: 'B' }))).toBe("## What went well\nA\n\n## What didn't\nB\n\n## Lessons for next projects\nC");
  });
  it('leaves out empty and blank boxes', () => {
    expect(writeSummary(boxes({ didnt: 'B', lessons: '   ' }))).toBe("## What didn't\nB");
  });
  it('keeps other notes after the boxes', () => {
    expect(writeSummary(boxes({ well: 'A' }), 'kept')).toBe('## What went well\nA\n\n## Other notes\nkept');
  });
  it('knows the limit', () => {
    expect(SUMMARY_LIMIT).toBe(16000);
  });
});

describe('parseSummary', () => {
  it('fills the three boxes', () => {
    const parsed = parseSummary("## What went well\nA\n\n## What didn't\nB\n\n## Lessons for next projects\nC");
    expect(parsed).toEqual({ boxes: { well: 'A', didnt: 'B', lessons: 'C' }, other: '', recognised: true });
  });
  it('reads a heading in other case and with a curly apostrophe', () => {
    const parsed = parseSummary('## WHAT WENT WELL  \nA\n\n## what didn’t\nB');
    expect(parsed.boxes).toEqual(boxes({ well: 'A', didnt: 'B' }));
  });
  it('keeps text before the first heading as other notes', () => {
    const parsed = parseSummary('Intro line\n\n## What went well\nA');
    expect(parsed.other).toBe('Intro line');
    expect(parsed.boxes.well).toBe('A');
  });
  it('keeps text under an unknown heading as other notes', () => {
    const parsed = parseSummary('## What went well\nA\n\n## Risks\nR1');
    expect(parsed.boxes.well).toBe('A');
    expect(parsed.other).toBe('## Risks\nR1');
  });
  it('shows a summary with no recognised heading whole', () => {
    const parsed = parseSummary('Just notes.\n\nSecond paragraph.');
    expect(parsed.recognised).toBe(false);
    expect(parsed.other).toBe('Just notes.\n\nSecond paragraph.');
    expect(parsed.boxes).toEqual(boxes({}));
  });
});

describe('round trip', () => {
  it('returns what a person typed, including blank lines', () => {
    const typed = boxes({ well: 'Line one\n\nLine two\n', didnt: '\nleading blank', lessons: 'tail\n\n' });
    expect(parseSummary(writeSummary(typed)).boxes).toEqual(typed);
  });
  it('returns one box alone', () => {
    const typed = boxes({ didnt: 'only this' });
    expect(parseSummary(writeSummary(typed)).boxes).toEqual(typed);
  });
  it('returns a whole summary unchanged when it is saved back as it is', () => {
    const whole = 'No headings here.\n\nAt all.';
    const parsed = parseSummary(whole);
    expect(parsed.recognised).toBe(false);
    expect(parsed.other).toBe(whole);
  });
  it('keeps other notes through a write and a read', () => {
    const first = parseSummary('Intro\n\n## What went well\nA');
    expect(parseSummary(writeSummary(first.boxes, first.other))).toEqual({ boxes: first.boxes, other: 'Intro', recognised: true });
  });
});

describe('hasHeadingLine', () => {
  it.each(['## What went well', "## What didn't", '## Lessons for next projects', '## what went well ', '## anything', '## Other notes'])('refuses %j', (line) => {
    expect(hasHeadingLine(`fine\n${line}\nfine`)).toBe(true);
  });
  it.each(['What went well', 'a ## b', '#hashtag', '### deeper'])('accepts %j', (line) => {
    expect(hasHeadingLine(line)).toBe(false);
  });
});
