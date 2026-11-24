// F-87: the work item's own controls as commands (POST /work/{id}/actions, /control, /background). One per control the API lists
// for this person; a control it does not list is not built. `adopt_profile`, `release_invoice` and every other value are ignored.
// None of these bodies has a key field or a case_revision (the contract forbids both), so there is no key; duplicates are
// stopped by the press lock, the uncertain lock and the revision check. A null revision stays null and holds every command.
import type { LiveWorkItem } from '@/api/types';

import { makeCommand, type CommandDescriptor } from './adapter';

export const NO_VERSION = 'We don’t have this item’s current version yet. Reload and try again.';

type Item = Pick<LiveWorkItem, 'id' | 'revision' | 'actions' | 'available_control'>;

export function workItemCommands(item: Item): CommandDescriptor[] {
  const base = `/api/v1/work/${item.id}`;
  const tokens = { expected_revision: item.revision };
  const hold = item.revision === null ? { disabledReason: NO_VERSION } : {};
  const out: CommandDescriptor[] = [];
  if (item.actions.includes('reconcile')) {
    out.push(makeCommand({ id: 'work.reconcile', label: 'Check what happened', url: `${base}/actions`, tokens, successStatuses: [202], ...hold }));
  }
  for (const [action, label] of [['resume', 'Resume'], ['cancel', 'Cancel']] as const) {
    if (item.available_control.includes(action)) out.push(makeCommand({ id: `work.${action}`, label, url: `${base}/control`, tokens, successStatuses: [200], ...hold }));
  }
  if (item.actions.includes('background')) {
    for (const [id, label] of [['pause', 'Pause background work'], ['continue', 'Continue background work']] as const) {
      const command = makeCommand({ id: `work.background.${id}`, label, url: `${base}/background`, tokens, action: null, successStatuses: [202], ...hold });
      // `enabled` is the descriptor's own field, so an input cannot flip it
      out.push({ ...command, body: (inputs) => ({ ...command.body(inputs), enabled: id === 'continue' }) });
    }
  }
  return out;
}
