// The retrospective's three boxes packed into the one live `summary` (D-8), and read back out.
// Written in this order, only for boxes with text, one blank line between sections:
//   ## What went well / ## What didn't / ## Lessons for next projects
// "## Other notes" holds text a saved summary carries outside the three boxes, so a new version never drops it.

export type BoxKey = 'well' | 'didnt' | 'lessons';
export type Boxes = Record<BoxKey, string>;
export type Parsed = { boxes: Boxes; other: string; recognised: boolean };

export const SUMMARY_LIMIT = 16000;
export const BOX_KEYS: readonly BoxKey[] = ['well', 'didnt', 'lessons'];
export const BOX_LABELS: Record<BoxKey, string> = { well: 'What went well', didnt: "What didn't", lessons: 'Lessons for next projects' };
export const EMPTY_BOXES: Boxes = { well: '', didnt: '', lessons: '' };
export const HEADING_MESSAGE = 'That line is a section heading. Reword it.';

const OTHER_LABEL = 'Other notes';
const SECTION_KEYS = [...BOX_KEYS, 'other'] as const;
type SectionKey = (typeof SECTION_KEYS)[number];
const HEADING_TEXT: Record<SectionKey, string> = { ...BOX_LABELS, other: OTHER_LABEL };

/** A line with straight apostrophes, no trailing spaces, lower case: the form a heading is compared in. */
const plain = (line: string) => line.replace(/[‘’]/g, "'").trimEnd().toLowerCase();
const HEADING_BY_PLAIN = new Map<string, SectionKey>(SECTION_KEYS.map((key) => [plain(`## ${HEADING_TEXT[key]}`), key]));
const sectionOf = (line: string): SectionKey | undefined => HEADING_BY_PLAIN.get(plain(line));
/** Any level-2 heading line, recognised or not. */
const isHeading = (line: string) => /^##\s/.test(line);

/** True when a line of a box would read back as a heading, so the text could not round-trip. */
export function hasHeadingLine(text: string): boolean {
  return text.split('\n').some(isHeading);
}

/** The summary text for the boxes (and the kept other notes). Empty boxes are left out. */
export function writeSummary(boxes: Boxes, other = ''): string {
  const parts: string[] = BOX_KEYS.filter((key) => boxes[key].trim() !== '').map((key) => `## ${BOX_LABELS[key]}\n${boxes[key]}`);
  if (other.trim() !== '') parts.push(`## ${OTHER_LABEL}\n${other}`);
  return parts.join('\n\n');
}

/**
 * The boxes of a saved summary. Text before the first recognised heading, and text under any other level-2 heading,
 * is "other"; a summary with no recognised heading is not split at all (`recognised: false`) and the caller shows it whole.
 */
export function parseSummary(summary: string): Parsed {
  const lines = summary.split('\n');
  if (!lines.some((line) => sectionOf(line) !== undefined)) return { boxes: { ...EMPTY_BOXES }, other: summary, recognised: false };
  type Segment = { key: SectionKey | 'stray'; lines: string[] };
  const segments: Segment[] = [{ key: 'stray', lines: [] }];
  for (const line of lines) {
    const key = sectionOf(line);
    if (key) segments.push({ key, lines: [] });
    else if (isHeading(line)) segments.push({ key: 'stray', lines: [line] });
    else segments[segments.length - 1].lines.push(line);
  }
  const boxes = { ...EMPTY_BOXES };
  const other: string[] = [];
  segments.forEach((segment, at) => {
    // The writer puts one blank line between sections: drop exactly that one, so what the person typed comes back as typed.
    const body = [...segment.lines];
    if (at < segments.length - 1 && body[body.length - 1] === '') body.pop();
    const text = body.join('\n');
    if (segment.key === 'stray' || segment.key === 'other') {
      if (text !== '') other.push(text);
    } else boxes[segment.key] = boxes[segment.key] ? `${boxes[segment.key]}\n${text}` : text;
  });
  return { boxes, other: other.join('\n'), recognised: true };
}
