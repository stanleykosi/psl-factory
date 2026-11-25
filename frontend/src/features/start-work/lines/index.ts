// The per-line registry. A line this screen can start has one entry here: its words, its fields, its required checks,
// the typed body it sends and the map from a server field name to a control. The chooser and the drawer shell read only
// this; adding a line (F-88 and later) is one file in this folder and one line in `FORMS`.
import type { ComponentType } from 'react';

import type { FieldValue, Values } from '../intake';
import type { MinutesPrepared } from '../engine/minutes';
import type { Line, Project, StartBody } from '../types';
import { pmoChange } from './pmoChange';
import { pmoEmergency } from './pmoEmergency';
import { pmoEscalation } from './pmoEscalation';
import { pmoIssues } from './pmoIssues';
import { pmoMinutes } from './pmoMinutes';
import { receivedBid } from './receivedBid';
import { weeklyReport } from './weeklyReport';

/** What the shell hands a line's fields. `errors` and `setValue` are by control name. */
export type LineFormProps = {
  values: Values;
  setValue: (name: string, value: FieldValue | undefined) => void;
  errors: Record<string, string>;
  readOnly: boolean;
  /** The chosen project's case, or null before one is chosen. */
  caseId: string | null;
  /** F-92: the served line (its `request_schema`), the whole chosen project, and where a read gives the case's newer revision. */
  line: Line;
  project: Project | null;
  onRevision: (caseRevision: number) => void;
};

/** What a start sends: `POST /work`'s body, or (minutes) the multipart parts built once so a resend is the same file and key. */
export type Prepared = StartBody | MinutesPrepared;

/** What a body needs from the shell: the chosen project and the one key for this body. */
export type StartContext = { caseId: string; caseRevision: number; idempotencyKey: string };

export type Missing = { name: string; label: string };

export type LineForm = {
  /** The live line key, e.g. 'pmo-weekly-report/v1'. */
  key: string;
  /** The primary button. */
  startLabel: string;
  drawerTitle: string;
  takesUpload?: boolean;
  /** Values cleared when the project changes (uploads and source records belong to one case). */
  projectBound?: string[];
  /** The line's controls below the project picker; the shell draws it and owns the start. */
  Form: ComponentType<LineFormProps>;
  /** The required controls left empty, in the order drawn (the project is checked by the shell). */
  missing(values: Values, line?: Line): Missing[];
  /** The body, exactly the line's schema branch. */
  buildBody(values: Values, ctx: StartContext, line?: Line): Prepared;
  /** F-92: replaces the default `POST /work` (minutes goes to its own route). It sends what `buildBody` made. */
  send?(prepared: Prepared): Promise<{ response: Response; data?: unknown; error?: unknown }>;
  /** F-92: false when the served schema is one this form cannot fully build; the chooser then lists the line as unavailable. */
  available?(line: Line): boolean;
  /** Which control a server field name belongs to: its control name, 'project' for the case, 'general' for a message
   *  with no control; undefined for a name this line does not know (drawn as its own box). */
  target(serverName: string, line?: Line): string | undefined;
};

/** What a line that owns its whole drawer is handed: the shell's way back and out, and where a signed-out person returns. */
export type OwnLineProps = { onBack: () => void; onClose: () => void; pathname: string };

/** A line with its own endpoint (the received RFP, F-88): `ownsSubmit` means the shell's project picker and `POST /work` are
 *  not used. It draws its drawer, sends its own request and is startable whatever `can_submit_via_api` says, once `GET /lines` lists it. */
export type OwnLine = {
  key: string;
  ownsSubmit: true;
  startLabel: string;
  drawerTitle: string;
  Own: ComponentType<OwnLineProps>;
};

const FORMS: LineForm[] = [weeklyReport, pmoIssues, pmoEscalation, pmoMinutes, pmoEmergency, pmoChange];
const OWN: OwnLine[] = [receivedBid];

export function lineFormFor(key: string): LineForm | undefined {
  return FORMS.find((form) => form.key === key);
}

export function ownLineFor(key: string): OwnLine | undefined {
  return OWN.find((line) => line.key === key);
}

