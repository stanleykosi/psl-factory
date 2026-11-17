// SCR-08 document review: the proposed E-DOCUMENT fields (mock/proposals/document-review.json, gaps G-SCR08-1..8), the
// checks on a response and the display text of each value. Pure functions only. Every value is shown as the response
// sends it: no check, count or diff is computed here, and a part the response lacks is left out or reads Unknown
// (INV-UNKNOWN). Section text is plain text; nothing here produces markup.
import type { operations } from '@/api/schema';
import { AGENT_NAMES, NOTE_MAX, type Verdict } from '@/features/decide/format';

export type TypedDocument = operations['E-DOCUMENT']['responses'][200]['content']['application/json'];

export type CheckStatus = 'done' | 'held' | 'blocked' | 'unknown';
export type DocNote = { agent: string; text: string; cites?: { label: string; reference: string }[] };
export type DocSection = { key: string; heading: string; text: string; changed_since?: boolean; notes?: DocNote[] };
export type DocCheck = { key: string; label: string; status?: string; detail?: string; cite?: string };
export type DocReturned = { by?: string; role?: string; at?: string; note?: string };

/** The typed fields plus the proposed ones, every proposed one optional. */
export type DocumentView = TypedDocument & {
  case_id?: string;
  project_title?: string;
  reference?: string;
  sections?: DocSection[];
  checks?: DocCheck[];
  audience?: { label?: string };
  review?: { role_label?: string; work_id?: string; task_id?: string };
  drafted_by?: { agent?: string; from?: string[] };
  returned?: DocReturned;
};

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
export const textOf = (value: unknown): string | undefined => (typeof value === 'string' && value.trim() !== '' ? value : undefined);

/** A 200 body without a document id, a title and a version (a misrouted response) is a load failure. */
export function isDocument(body: unknown): body is DocumentView {
  if (!isObject(body)) return false;
  return typeof body.document_id === 'string' && typeof body.title === 'string' && typeof body.version === 'string';
}

/** `v` from the URL: a positive whole number as text ("2"); anything else (missing, "latest", "2.5", "02") is null. */
export function parseVersion(value: string | null | undefined): string | null {
  return typeof value === 'string' && /^[1-9]\d{0,8}$/.test(value) ? value : null;
}

/** Sections that carry a heading and text; undefined when the response has no `sections` array at all. */
export function sectionsOf(doc: DocumentView): DocSection[] | undefined {
  if (!Array.isArray(doc.sections)) return undefined;
  return doc.sections.filter((s): s is DocSection => isObject(s) && typeof s.key === 'string' && typeof s.heading === 'string' && typeof s.text === 'string');
}

/** The notes of a section that have text. */
export const notesOf = (section: DocSection): DocNote[] =>
  Array.isArray(section.notes) ? section.notes.filter((n): n is DocNote => isObject(n) && typeof n.agent === 'string' && textOf(n.text) !== undefined) : [];

/** Paragraphs split on blank lines; plain text only. */
export const paragraphsOf = (text: string): string[] => text.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);

/** Checks in the order sent that have a key and a label. */
export const checksOf = (doc: DocumentView): DocCheck[] =>
  Array.isArray(doc.checks) ? doc.checks.filter((c): c is DocCheck => isObject(c) && typeof c.key === 'string' && textOf(c.label) !== undefined) : [];

export const CHECK_WORDS: Record<CheckStatus, string> = { done: 'Done', held: 'Held', blocked: 'Blocked', unknown: 'Unknown' };
const isCheckStatus = (status: unknown): status is CheckStatus => typeof status === 'string' && Object.hasOwn(CHECK_WORDS, status);

/** The status as the four words; absent or any other value reads Unknown (never a made-up "Done"). */
export const checkStatus = (check: Pick<DocCheck, 'status'>): CheckStatus => (isCheckStatus(check.status) ? check.status : 'unknown');

export type CheckTone = 'done' | 'waiting' | 'person' | 'neutral';
const CHECK_TONES: Record<CheckStatus, CheckTone> = { done: 'done', held: 'waiting', blocked: 'person', unknown: 'neutral' };
export const checkTone = (check: Pick<DocCheck, 'status'>): CheckTone => CHECK_TONES[checkStatus(check)];

/**
 * The tag on a check. Done shows the backend's own detail ("Matches COST-0140 v2") or the word Done; Held, Blocked and
 * Unknown always show their word, with the detail (the reason) beside it as plain text, so no detail can read as a pass.
 */
export function checkTag(check: DocCheck): { text: string; reason?: string } {
  const status = checkStatus(check);
  const detail = textOf(check.detail);
  return status === 'done' ? { text: detail ?? CHECK_WORDS.done } : { text: CHECK_WORDS[status], reason: detail };
}

/** The phone's one tag: the `amounts` check in the same words. Undefined when the response has no such check. */
export function amountsTag(doc: DocumentView): { text: string; tone: CheckTone } | undefined {
  const check = checksOf(doc).find((c) => c.key === 'amounts');
  if (!check) return undefined;
  const text = checkTag(check).text;
  // a held, blocked or unknown amount names what it is about; a done one is the backend's own sentence
  return { text: checkStatus(check) === 'done' ? text : `Amounts: ${text}`, tone: checkTone(check) };
}

const AGENT_KEYS = Object.keys(AGENT_NAMES);
/** "Tola" for the key `tola`; any other agent text as it came. */
export const agentName = (agent: string): string => (AGENT_KEYS.includes(agent) ? AGENT_NAMES[agent as keyof typeof AGENT_NAMES] : agent);

/** "Drafted by Tola from the planning record and the approved costing."; undefined without an agent. */
export function draftedByText(doc: DocumentView): string | undefined {
  const agent = textOf(doc.drafted_by?.agent);
  if (!agent) return undefined;
  const from = (Array.isArray(doc.drafted_by?.from) ? doc.drafted_by.from : []).filter((f) => textOf(f));
  const list = from.length <= 1 ? from.join('') : `${from.slice(0, -1).join(', ')} and ${from[from.length - 1]}`;
  return `Drafted by ${agentName(agent)}${list ? ` from ${list}` : ''}.`;
}

/** The first note of the first section that has one, with that section's number (its place in the list). */
export function firstFlag(sections: DocSection[]): { agent: string; number: number; text: string } | undefined {
  for (const [i, section] of sections.entries()) {
    const note = notesOf(section)[0];
    if (note) return { agent: agentName(note.agent), number: i + 1, text: note.text };
  }
  return undefined;
}

/** "Returned by Kemi Adebayo (PMO Lead)"; the parts the response lacks are left out. */
export function returnedByText(returned: DocReturned): string {
  const by = textOf(returned.by);
  const role = textOf(returned.role);
  if (!by) return role ? `Returned by ${role}` : 'Returned';
  return role ? `Returned by ${by} (${role})` : `Returned by ${by}`;
}

/** The note rule, one for both pages: approve sends no note; return needs a note of 1 to NOTE_MAX characters. */
export function noteProblem(verdict: Verdict, note: string): string | null {
  if (note.length > NOTE_MAX) return `Keep the note to ${NOTE_MAX} characters or fewer.`;
  if (verdict !== 'approve' && note.trim() === '') return 'Add a note to return it.';
  return null;
}

export const documentHref = (caseId: string, documentId: string, version: string) =>
  `/projects/${encodeURIComponent(caseId)}/documents/${encodeURIComponent(documentId)}?v=${encodeURIComponent(version)}`;

/** A link target the page may render: http(s) or a relative path. Anything else (javascript:, data:, //host) is not a link. */
export function isLinkUrl(value: unknown): value is string {
  if (typeof value !== 'string' || value.trim() === '') return false;
  const url = value.trim();
  if (/^https?:\/\//i.test(url)) return true;
  return url.startsWith('/') ? !url.startsWith('//') && !url.startsWith('/\\') : !/^[a-z][a-z0-9+.-]*:/i.test(url) && !url.startsWith('\\');
}
