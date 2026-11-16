// PROPOSAL (D-LINE-WORKSPACE, contract mock only): two fields the frame reads ahead of the contract. They live in the
// mock fixtures and in this one typed reader; the generated types and openapi.json do not carry them, and the backend
// developer may change or refuse either (G-SCR28-1, G-SCR28-3). An absent or malformed value reads as "not supplied".
import type { Step, Workspace } from './labels';

/** G-SCR28-1 `steps[].items_default: "checked"`: the target items of an `items` step start ticked. Absent means unticked. */
export const itemsDefaultChecked = (step: Step): boolean => (step as { items_default?: unknown }).items_default === 'checked';

/** X-LINKS (G-SCR28-3) `workspace.links[]`: only the two kinds the frame draws; any other kind is not drawn. */
export type WorkspaceLink =
  | { key: string; label: string; kind: 'assistant' }
  | { key: string; label: string; kind: 'document'; documentId: string; version: string };

const text = (value: unknown): value is string => typeof value === 'string' && value.trim() !== '';

export function workspaceLinks(workspace: Workspace): WorkspaceLink[] {
  const list = (workspace as { links?: unknown }).links;
  if (!Array.isArray(list)) return [];
  const links: WorkspaceLink[] = [];
  for (const entry of list as { key?: unknown; label?: unknown; target?: { kind?: unknown; document_id?: unknown; version?: unknown } }[]) {
    if (!text(entry?.key) || !text(entry.label) || typeof entry.target !== 'object' || entry.target === null) continue;
    const { key, label } = entry;
    const { kind, document_id: documentId, version } = entry.target;
    if (kind === 'assistant') links.push({ key, label, kind });
    else if (kind === 'document' && text(documentId) && (text(version) || typeof version === 'number')) links.push({ key, label, kind, documentId, version: String(version) });
  }
  return links;
}
