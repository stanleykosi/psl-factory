// What the thread draws from a message, pure. Everything comes from the record read; nothing is worked out from
// roles or from the agent's words.
import type { AgentRunStatus, AgentStep } from '@/components';

import type { Message } from './types';

type Ref = NonNullable<NonNullable<Message['step_details']>[number]['reference']>;

export const workHref = (id: string) => `/work/${encodeURIComponent(id)}`;
export const caseHref = (id: string) => `/projects/${encodeURIComponent(id)}`;

/** The words of a reference: its label, else its reference. */
export const refWords = (ref: Ref | undefined): string | undefined => ref?.label ?? ref?.reference;

/** step_details as checklist steps; without them the plain `steps` strings, shown as done. */
export function stepsOf(message: Message, link: (ref: Ref, words: string) => AgentStep['source']): AgentStep[] {
  if (message.step_details) {
    // A step that names a record the person may not see (the same words as a restricted source) shows no record.
    const hidden = new Set(message.source_details?.filter((s) => s.restricted).flatMap((s) => [s.label, s.reference]).filter(Boolean));
    return message.step_details.map((step) => {
      const words = refWords(step.reference);
      const shown = step.reference && words && !hidden.has(words);
      return { text: step.text, status: step.state, source: shown ? link(step.reference!, words) : undefined };
    });
  }
  return message.steps.map((text) => ({ text, status: 'done' as const }));
}

export const runStatus = (steps: AgentStep[]): AgentRunStatus => (steps.some((s) => s.status !== 'done') ? 'working' : 'done');

export type SourceView = { key: string; label?: string; href?: string; restricted: boolean };

/** source_details, else sources: a restricted source keeps nothing of the record. */
export function sourcesOf(message: Message): SourceView[] {
  if (message.source_details) {
    return message.source_details.map((source, at) => {
      if (source.restricted) return { key: `r${at}`, restricted: true };
      const link = source.link;
      const href = link?.work_id ? workHref(link.work_id) : link?.case_id ? caseHref(link.case_id) : undefined;
      return { key: `s${at}`, label: source.label, href, restricted: false };
    });
  }
  return message.sources.map((source, at) =>
    source.restricted ? { key: `r${at}`, restricted: true } : { key: `s${at}`, label: `${source.kind} · ${source.reference}`, restricted: false },
  );
}
