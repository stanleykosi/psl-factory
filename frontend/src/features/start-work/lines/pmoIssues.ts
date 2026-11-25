// F-92: Chase an open issue. The schema's one leaf is the issue; the server derives the reference.
import { engineForm } from '../engine/engine';

export const pmoIssues = engineForm({
  key: 'pmo-issues/v1',
  drawerTitle: 'Chase an open issue',
  startLabel: 'Start chase',
  labels: { issue_id: { label: 'Issue' } },
  sources: { issue_id: { kind: 'sources', field: 'issue_id' } },
  needs: ['issue_id'],
});
