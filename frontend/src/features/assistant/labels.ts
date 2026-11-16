// Words for the assistant page. The agent hello, ability lines and placeholders are frontend-owned copy for the
// contract mock (G-SCR05-6; the backend should own them). The neutral sentences are not business rules.
import { formatDayMonth } from '@/components';

import type { AgentName, Conversation, ConversationRow } from './types';

export const HOME_ABILITY: Record<AgentName, string> = {
  tola: 'I draft plans, SOWs, status reports and minutes, chase sign-offs, and explain where any project stands.',
  chidi: 'I draft invoices from completed milestones, answer questions about a project’s money, and explain what is holding a payment.',
  zainab: 'I match staff records for payroll, prepare HR summaries and answer HR questions, and I keep private details private.',
};

export const PLACEHOLDER: Record<AgentName, string> = {
  tola: 'Ask Tola to draft a SOW, plan or report, or ask about a project…',
  chidi: 'Ask Chidi to draft an invoice, or ask about a project’s billing…',
  zainab: 'Ask Zainab about staff matching or payroll preparation…',
};

export function hello(agent: AgentName, firstName: string): string {
  if (agent === 'tola') return `Hi ${firstName}, I’m Tola. What should we get moving?`;
  if (agent === 'chidi') return 'Hi, I’m Chidi. What do you need from Finance?';
  return 'Hi, I’m Zainab. How can I help with people and payroll?';
}

export const LIST_NOTE = 'Agents use only records you can see. Everything they create is a draft that goes through the usual review.';
export const CANNOT_NOTE = 'Agents draft, read and explain. They cannot approve, send, pay or change a record.';
export const TEXT_LIMIT = 4000;
export const TOO_LONG = 'Keep it under 4,000 characters.';
export const NO_AGENTS = 'No agents are available to you.';
export const NO_CONVERSATIONS = 'No conversations yet.';
export const NOT_FOUND = 'We could not find that conversation.';
export const CHANGED = 'This conversation changed. Showing the latest.';
export const REFRESH_FAILED = 'Couldn’t refresh. Retrying.';
export const SEND_UNSURE = 'We couldn’t confirm that was sent.';
export const NOTHING_TO_MENTION = 'Nothing you can mention matches.';
export const MENTION_FAILED = 'Couldn’t load. Try again.';
export const HELD_MIC = 'Not available yet';

const STATUS_WORDS: Record<ConversationRow['status'], string> = {
  working: 'Working',
  answered: 'Answered',
  cannot_answer: 'Can’t answer',
  drafted: 'Drafted',
};

export const statusLine = (row: Pick<ConversationRow, 'status' | 'status_line'>) => row.status_line ?? STATUS_WORDS[row.status];

/** The side panel's sentence for a conversation (spec: E-CONVERSATION table). */
export function sideSentence(name: string, conversation: Pick<Conversation, 'status' | 'messages'>): string | undefined {
  switch (conversation.status) {
    case 'working':
      return `${name} is working on it. You can leave; you’ll be alerted.`;
    case 'answered':
      return `${name} answered from records you can see.`;
    case 'cannot_answer':
      return `${name} can’t do that with your access.`;
    case 'drafted': {
      const started = conversation.messages.some((m) => m.draft?.started);
      return started ? `${name} answered from records you can see.` : `${name} has a draft ready for you to check.`;
    }
    default:
      return undefined;
  }
}

const LAGOS_DAY = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Lagos', year: 'numeric', month: '2-digit', day: '2-digit' });
const dayOf = (value: string | number | Date) => LAGOS_DAY.format(new Date(value));

/** "TODAY", "YESTERDAY" or "12 NOV" for a list row, read against when the list was read (Africa/Lagos days). */
export function dayLabel(updatedAt: string, asOf: string): string {
  const day = dayOf(updatedAt);
  const today = dayOf(asOf);
  if (day === today) return 'TODAY';
  if (day === dayOf(new Date(asOf).getTime() - 24 * 60 * 60 * 1000)) return 'YESTERDAY';
  return formatDayMonth(updatedAt).toUpperCase();
}

/** The rows in the order returned, as consecutive groups by day. */
export function groupByDay(rows: ConversationRow[], asOf: string): { label: string; rows: ConversationRow[] }[] {
  const groups: { label: string; rows: ConversationRow[] }[] = [];
  for (const row of rows) {
    const label = dayLabel(row.updated_at, asOf);
    const last = groups[groups.length - 1];
    if (last?.label === label) last.rows.push(row);
    else groups.push({ label, rows: [row] });
  }
  return groups;
}
