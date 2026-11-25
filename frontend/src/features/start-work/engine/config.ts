// F-92: what a line adds to its served `request_schema`: words, order, parents and where a record's choices come from. Required,
// nullable, the allowed values and the lengths are never written here; the schema gives them.
export type Source =
  /** `GET /projects/{case_id}/intake-sources?field=<field>` */
  | { kind: 'sources'; field: string }
  /** The project's `workflow_intake_url` (the escalation register's `requests`). */
  | { kind: 'escalations' };

export type EngineConfig = {
  /** The live line key, e.g. 'pmo-issues/v1'. */
  key: string;
  drawerTitle: string;
  startLabel: string;
  /** A prefix of the schema path dropped from control names (minutes' `data.`), so the 422 names are the form's own. */
  strip?: string;
  /** Schema paths this form neither draws nor sends (the JSON route's `data.evidence_id`, which the upload route does not take). */
  skip?: string[];
  /** The controls by name (the path without `strip`), in the order drawn. A schema leaf that is not here makes the line unsupported. */
  labels: Record<string, { label: string; help?: string }>;
  /** A control that waits for another (name to its parent's name). */
  parents?: Record<string, string>;
  /** The record controls and where their choices come from. */
  sources: Record<string, Source>;
  /** Controls the schema must carry for the line to be drawn at all. */
  needs: string[];
  /** The notes file route (minutes): the file control's name and label; the start is sent as multipart to the project's minutes route. */
  upload?: { name: string; label: string };
};
