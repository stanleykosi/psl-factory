// F-92: Record an emergency. Authorisation and outcome belong to the chosen emergency record.
import { engineForm } from '../engine/engine';

export const pmoEmergency = engineForm({
  key: 'pmo-emergency/v1',
  drawerTitle: 'Record an emergency',
  startLabel: 'Start emergency',
  labels: {
    profile_id: { label: 'Emergency record' },
    'inputs.authorization_id': { label: 'Authorisation' },
    'inputs.outcome_id': { label: 'Outcome' },
    'inputs.template_id': { label: 'Template' },
    'inputs.audience': { label: 'Audience' },
  },
  parents: { 'inputs.authorization_id': 'profile_id', 'inputs.outcome_id': 'profile_id' },
  sources: {
    profile_id: { kind: 'sources', field: 'profile_id' },
    'inputs.authorization_id': { kind: 'sources', field: 'inputs.authorization_id' },
    'inputs.outcome_id': { kind: 'sources', field: 'inputs.outcome_id' },
    'inputs.template_id': { kind: 'sources', field: 'inputs.template_id' },
  },
  needs: ['profile_id'],
});
