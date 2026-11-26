// F-94: Prepare an invoice. Two ways in, as the schema's `mode` says: a completed milestone's coverage and handoff, or an existing
// billing preparation (with its invoice and due date, both optional). No amount is asked for or shown here.
import { engineForm } from '../engine/engine';

export const pmoFinance = engineForm({
  key: 'pmo-finance/v1',
  drawerTitle: 'Prepare an invoice',
  startLabel: 'Start invoice',
  labels: {
    mode: { label: 'Start from', valueLabels: { completion: 'A completed milestone', preparation: 'An existing preparation' } },
    coverage_id: { label: 'Billing coverage' },
    handoff_id: { label: 'Milestone handoff' },
    preparation_id: { label: 'Billing preparation' },
    invoice_id: { label: 'Invoice' },
    due_date: { label: 'Due date' },
  },
  parents: { invoice_id: 'preparation_id' },
  sources: {
    coverage_id: { kind: 'sources', field: 'coverage_id' },
    handoff_id: { kind: 'sources', field: 'handoff_id' },
    preparation_id: { kind: 'sources', field: 'preparation_id' },
    invoice_id: { kind: 'sources', field: 'invoice_id' },
  },
  needs: ['mode'],
});
