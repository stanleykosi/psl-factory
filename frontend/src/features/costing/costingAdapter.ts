// F-99: the costing panel (key 'bid-pricing', GET /work/{id}/bid-pricing) on the live work item. The rule used comes from the
// project's costing read; when that read fails the rest of the panel still draws. Writes are described in model.ts and drawn by
// CostingActions; sent by useWorkCommand.
import { call, liveApi } from '@/api/client';
import { readPanel, registerLineAdapter, type LineAdapter, type LineContext, type PanelRef } from '@/features/workspace/adapter';

import { CostingActions } from './CostingActions';
import { costingCommands, costingSections, type Costing, type Pricing, type Readback } from './model';

async function read(ref: PanelRef, ctx?: LineContext): Promise<Readback> {
  const pricing = await readPanel<Pricing>(ref);
  const costing: Costing | null = ctx ? await call(liveApi.GET('/api/v1/projects/{case_id}/costing', { params: { path: { case_id: ctx.caseId } } })).catch(() => null) : null;
  return { pricing, costing };
}

export const costingAdapter: LineAdapter<Readback> = {
  key: 'bid-pricing',
  read,
  sections: (readback) => costingSections(readback),
  commands: (readback, ctx) => costingCommands(readback, ctx),
  Actions: CostingActions,
};

registerLineAdapter(costingAdapter as LineAdapter);
