// F-102: Start the fixed asset schedule. The register is the one required record; the prior schedule and the ledger mapping are optional.
import { engineForm } from '../engine/engine';

export const financePpe = engineForm({
  key: 'finance-ppe/v1',
  drawerTitle: 'Fixed asset schedule',
  startLabel: 'Start schedule',
  labels: { register_id: { label: 'Register' }, prior_id: { label: 'Prior schedule' }, ledger_id: { label: 'Ledger mapping' } },
  sources: { register_id: { kind: 'sources', field: 'register_id' }, prior_id: { kind: 'sources', field: 'prior_id' }, ledger_id: { kind: 'sources', field: 'ledger_id' } },
  needs: ['register_id'],
});
