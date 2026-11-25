// F-92: Minutes after a meeting. The served schema is the JSON route's (`intake.data`); the notes file route takes the same
// template, meeting and audience as its own parts, so those leaves are read from `data` and the rest of `data` (the protocol, the
// evidence id, the publish flag) is left out. The notes file goes with the start to the project's minutes route.
import { engineForm } from '../engine/engine';

export const pmoMinutes = engineForm({
  key: 'pmo-minutes/v1',
  drawerTitle: 'Minutes after a meeting',
  startLabel: 'Start minutes',
  strip: 'data.',
  skip: ['data.protocol', 'data.evidence_id', 'data.publish'],
  labels: { template_id: { label: 'Template' }, meeting_version_id: { label: 'Meeting' }, audience: { label: 'Audience' } },
  sources: { template_id: { kind: 'sources', field: 'data.template_id' }, meeting_version_id: { kind: 'sources', field: 'data.meeting_version_id' } },
  needs: ['template_id', 'audience'],
  upload: { name: 'notes_file', label: 'Notes file' },
});
