// F-92: Escalate an issue. The request is one the project's escalation register already holds; the template is optional.
import { engineForm } from '../engine/engine';

export const pmoEscalation = engineForm({
  key: 'pmo-escalation/v1',
  drawerTitle: 'Escalate an issue',
  startLabel: 'Start escalation',
  labels: { request_id: { label: 'Escalation request' }, template_id: { label: 'Template' } },
  sources: { request_id: { kind: 'escalations' }, template_id: { kind: 'sources', field: 'template_id' } },
  needs: ['request_id'],
});
