// F-136: the client's response and SOW signature panel (key 'commercial-response', GET /projects/{case_id}/commercial-response) on
// the live work item. Writes are described in commercialModel.ts and drawn by CommercialActions; sent by useWorkCommand.
import { readPanel, registerLineAdapter, type LineAdapter } from '@/features/workspace/adapter';

import { CommercialActions } from './CommercialActions';
import { commercialCommands, commercialSections, type CommercialDesk } from './commercialModel';

export const commercialAdapter: LineAdapter<CommercialDesk> = {
  key: 'commercial-response',
  read: (ref) => readPanel<CommercialDesk>(ref),
  sections: (desk) => commercialSections(desk),
  commands: (desk, ctx) => commercialCommands(desk, ctx),
  Actions: CommercialActions,
};

registerLineAdapter(commercialAdapter as LineAdapter);
