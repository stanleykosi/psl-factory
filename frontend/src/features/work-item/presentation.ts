// PROPOSAL (D-WORKITEM-VIEW): board detail that E-WORK-ITEM and E-WORK-HISTORY have no field for yet.
// Typed here only; read from the response with a safe cast and hidden when absent, so live responses
// (which never carry it) render exactly as before. Presentation only: nothing here decides access,
// authority or business state, and a contract field always wins where one exists.
import type { FactName, HistoryEntry, HistoryKind, WorkItem } from './labels';

export type PanelTone = 'dark' | 'signal' | 'waiting' | 'verified';
export type PanelLink = { label: string; href: string; primary?: boolean };

export type WorkItemPresentation = {
  /** Phone history back link, e.g. "Invoice"; "Work item" when absent. */
  back_label?: string;
  /** The line above the title on the state boards ("INV-0412 · LAGOON HEALTH"); the breadcrumb when absent. */
  eyebrow?: string;
  /** Wording the phone boards draw differently ("M2 invoice"); each field replaces the desktop one below 720px. */
  phone?: PhonePresentation;
  /** Visible detail per fact ("v2", "Ada", "To client 06 Nov"); an unknown fact still reads Unknown. */
  facts?: Partial<Record<FactName, string>>;
  /** Visible detail per station index ("Approved 10:47", "Held · no reviewer"). */
  stations?: (string | null)[];
  /** Phone only: the boards draw just the first N stations (the others stay for screen readers). */
  stations_shown?: number;
  agent?: {
    /** "Finance agent", "PMO agent". */
    role?: string;
    /** The phone boards' one-line agent note. */
    summary?: string;
    /** Bold first line of the waiting banner. */
    headline?: string;
    /** The limits line the default board draws at the end of the agent's head ("Prepares drafts. Cannot approve, send or pay."). */
    limits?: string;
    /** Phone: the note is drawn without the agent's name and role. */
    plain?: boolean;
    /** The agent card text, one entry per paragraph. */
    message?: string[];
  };
  /** The board's state card: the right column on desktop, a block or callout on phones. */
  panel?: {
    title: string;
    tone?: PanelTone;
    /** Bold first line. */
    lead?: string;
    body: string[];
    /** A recorded reason, shown as "Reason: …". */
    quote?: string;
    rows?: { label: string; value: string }[];
    /** Small print under the links. */
    note?: string;
    /** The board sets this card's heading larger, so it wraps in the narrow column. */
    large_title?: boolean;
    /** Phone: the board pins a bar here whose control belongs to another feature; the bar's room is kept. */
    bar_slot?: boolean;
    /** Phone: small print under the bar's buttons. */
    bar_note?: string;
    /** Navigation only: rendered when the href is an app path. */
    links?: PanelLink[];
    /** The phone boards' shorter version; a callout when `kind` is set, else a plain line. */
    summary?: { text: string; kind?: 'info' | 'warning' | 'problem' };
  };
  /** The issue board's invoice preview, drawn on PSL's test template. */
  preview?: {
    template_label: string;
    brand: string;
    bill_to: { name: string; email: string };
    number: string;
    issue_note: string;
    lines: { description: string; detail?: string; amount: string }[];
    tax: string;
    footer: string;
    /** The phone summary card: version and basis lines. */
    version: string;
    basis: string;
  };
  /** Small print under the decision panel. */
  task_note?: string;
  /** Entry counts per history filter, for the tab and filter badges. */
  history_counts?: Record<HistoryKind, number>;
};

export type PhonePresentation = Partial<Pick<WorkItemPresentation, 'facts' | 'stations' | 'stations_shown' | 'agent' | 'panel' | 'preview'>> & {
  /** The phone boards' shorter title ("Lagoon Health · M2 invoice"). */
  title?: string;
};

/** The presentation as seen at this width: below 720px the phone block's fields replace the desktop ones. */
export function viewFor(view: WorkItemPresentation | undefined, phone: boolean): WorkItemPresentation | undefined {
  if (!view || !phone || !view.phone) return view;
  // the phone title is read by the header; the rest replaces the desktop fields
  const over: Partial<WorkItemPresentation> = { ...view.phone };
  delete (over as { title?: string }).title;
  return { ...view, ...over, agent: { ...view.agent, ...over.agent } };
}

/** PROPOSAL: extra detail lines on a history entry ("Note: …", "Used: …"). */
export type BoardHistoryEntry = HistoryEntry & { lines?: string[] };

/** The `presentation` block of a work item response, if the response carries one. */
export function presentationOf(item: WorkItem): WorkItemPresentation | undefined {
  const value = (item as WorkItem & { presentation?: unknown }).presentation;
  return value && typeof value === 'object' ? (value as WorkItemPresentation) : undefined;
}

/** Only app paths ("/setup") are links; absolute, protocol-relative and script hrefs are dropped. */
export function isAppPath(href: string): boolean {
  return /^\/(?!\/)/.test(href) && !/[\s\\]/.test(href);
}
