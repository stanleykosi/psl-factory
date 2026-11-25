// F-92: Start a change. Authorisation belongs to the chosen change version.
import { engineForm } from '../engine/engine';

export const pmoChange = engineForm({
  key: 'pmo-change/v1',
  drawerTitle: 'Start a change',
  startLabel: 'Start change',
  labels: {
    version_id: { label: 'Change version' },
    'inputs.authorization_id': { label: 'Authorisation' },
    'inputs.template_id': { label: 'Template' },
  },
  parents: { 'inputs.authorization_id': 'version_id' },
  sources: {
    version_id: { kind: 'sources', field: 'version_id' },
    'inputs.authorization_id': { kind: 'sources', field: 'inputs.authorization_id' },
    'inputs.template_id': { kind: 'sources', field: 'inputs.template_id' },
  },
  needs: ['version_id'],
});
