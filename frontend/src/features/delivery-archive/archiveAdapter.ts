// F-116: the archive line (delivery-archive/v1, SCR-47). One panel, `archive-files`: the inventory, its status sentence and index (sections)
// and the start and per-file checks (ArchiveActions). Writes are described in archiveModel.ts.
import { readPanel, registerLineAdapter, type LineAdapter } from '@/features/workspace/adapter';

import { ArchiveActions } from './ArchiveActions';
import { archiveCommands, archiveSections, type Archive } from './archiveModel';

export const archiveAdapter: LineAdapter<Archive> = {
  key: 'archive-files',
  read: (ref) => readPanel<Archive>(ref),
  sections: archiveSections,
  commands: archiveCommands,
  Actions: ArchiveActions,
};

registerLineAdapter(archiveAdapter as LineAdapter);
