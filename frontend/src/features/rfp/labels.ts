// RFP values to the words on the SCR-16 boards. Presentation only: which results, reasons and roles are offered,
// and who may record or send, come from the API.
import type { OutcomeResult, Rfp } from './contract';

/** The result words the boards use (results is an enum with no labels). */
export const RESULT_LABELS: Record<OutcomeResult, string> = { won: 'Won', lost: 'Lost', pending: 'Pending', unknown: 'Unknown' };

export const RECORD_LABELS: Record<OutcomeResult, string> = {
  won: 'Record won',
  lost: 'Record lost',
  pending: 'Record pending',
  unknown: 'Save as unknown',
};

/** The recorded state's heading; an unknown result string reads "Outcome recorded". */
export function recordedHeading(result: string): string {
  const words: Record<string, string> = { won: 'Won', lost: 'Lost', pending: 'Decision pending', unknown: 'Outcome unknown' };
  return words[result] ?? 'Outcome recorded';
}

/** The phone bar's note on recorded states. */
export const resultNote = (result: string) => (result in RESULT_LABELS ? result.toUpperCase() : undefined);

/** The frame's status tag tone, by kind only (nothing derived from days_left or at). Lost is grey and unknown amber, as the boards draw them. */
export function statusTone(kind: Rfp['status']['kind']): string {
  if (kind === 'deadline' || kind === 'pending' || kind === 'unknown') return 'psl-tag--waiting';
  if (kind === 'won') return 'psl-tag--done';
  return 'psl-tag--neutral';
}

/** "Tamarind Loans · loan origination RFP", or whichever of the two is present. */
export function frameHeading(rfp: Rfp): string | undefined {
  return [rfp.client, rfp.title].filter(Boolean).join(' · ') || undefined;
}

/**
 * An awarded amount as typed, to the request's decimal string: the ₦ sign, spaces and commas are dropped and a
 * whole number gets ".00". Undefined when the text is not an amount (letters, more than two decimals).
 */
export function amountValue(text: string): string | undefined {
  const plain = text.replace(/[₦,\s]/g, '');
  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(plain);
  if (!match) return undefined;
  const whole = match[1].replace(/^0+(?=\d)/, '');
  return `${whole}.${(match[2] ?? '').padEnd(2, '0')}`;
}
