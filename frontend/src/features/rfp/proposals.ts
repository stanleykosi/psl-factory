// PROPOSAL (F-36, contract mock only): three optional keys on E-WORK-ITEM `assign` that the "Assign accountable PM" panel reads ahead of the
// contract. They live in the mock fixtures (mock/proposals/rfp-assign.json) and in these typed readers; the generated types and openapi.json
// do not carry them, and the backend developer may change or refuse any (G-24-1, G-24-2, G-24-3). An absent or malformed value reads as "not supplied".

const text = (value: unknown): value is string => typeof value === 'string' && value.trim() !== '';
const read = (assign: object, key: string): unknown => (assign as Record<string, unknown>)[key];

/** G-24-1 `assign.roles[]`: the roles the assigner may act in, as {role, label}. A malformed entry is skipped; none left reads as not supplied. */
export function assignRoles(assign: object): { role: string; label: string }[] | undefined {
  const list = read(assign, 'roles');
  if (!Array.isArray(list)) return undefined;
  const roles = list.flatMap((entry: { role?: unknown; label?: unknown } | null) => (text(entry?.role) && text(entry.label) ? [{ role: entry.role, label: entry.label }] : []));
  return roles.length > 0 ? roles : undefined;
}

/** G-24-2 `assign.evidence_kind`: the kind of proof an assignment may carry. Absent: no Proof field. */
export const assignEvidenceKind = (assign: object): string | undefined => {
  const kind = read(assign, 'evidence_kind');
  return text(kind) ? kind : undefined;
};

/** G-24-3 `assign.next`: the backend's own "What happens next" sentences, shown as returned. `channels` is not drawn on its own. */
export function assignNext(assign: object): { summary: string; agent?: string } | undefined {
  const next = read(assign, 'next') as { summary?: unknown; agent?: unknown } | null | undefined;
  if (typeof next !== 'object' || next === null || !text(next.summary)) return undefined;
  return { summary: next.summary, ...(text(next.agent) ? { agent: next.agent } : {}) };
}
