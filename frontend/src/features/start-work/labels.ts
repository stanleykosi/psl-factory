// Start work copy. Presentation only: words the drawer says that no contract field carries, plus the per-line choices
// IntakeField still reads for the v7 fields StepForm draws.

/** The chooser's line for a line this screen cannot start, and its link (LC-Q3 option 1). */
export const UNAVAILABLE_NOTE = 'Not available here yet. Open it in the full form.';
export const UNAVAILABLE_LINK = 'Open in the full form';
/** A 409: nothing was started; the project moved on. */
export const CHANGED_SINCE_OPENED = 'This project changed since you opened it.';
export const RECORD_UNAVAILABLE = 'This record is unavailable.';

/** Lines whose board draws a four-way choice as joined segments instead of a select (SCR-23's submission method). */
const FOUR_SEGMENTS = new Set(['rfp_intake']);

/** Fields the boards draw as a select though they have few options, by line key (SCR-04-*-ppe "Accounting note"). */
const SELECT_CHOICES: Record<string, string[]> = { fixed_assets: ['accounting_note'] };

/** Lines whose optional record and choice fields read "Optional" as a muted line under the control, as the F-51 boards
 *  draw them, instead of "(optional)" in the label. */
const OPTIONAL_LINE = new Set(['fixed_assets']);

/** Under the Proof box after the project changed: the file was uploaded to the other project's case (Conflicts 4). */
export const PROOF_MOVED = 'Proof removed: it was added to the other project. Add it again.';
/** F-09's 403 sentence (useEvidenceUpload), also shown for a 404 so the two can't be told apart. */
export const CANT_ADD = 'You can’t add proof to this item.';

export function fourSegments(lineKey: string): boolean {
  return FOUR_SEGMENTS.has(lineKey);
}

export function selectChoice(lineKey: string, field: string): boolean {
  return SELECT_CHOICES[lineKey]?.includes(field) ?? false;
}

export function optionalAsLine(lineKey: string): boolean {
  return OPTIONAL_LINE.has(lineKey);
}

