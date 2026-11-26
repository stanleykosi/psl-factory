// F-115: the hypercare line (delivery-hypercare/v1, SCR-46). Two panels, each with its own adapter: `stability` (the result, criteria, checks
// and readings; its Actions draw the open issues and the next step) and `stability/events` (release and acceptance, display only).
// No write is described here; pause and continue are the work item's own controls.
import { readPanel, registerLineAdapter, type LineAdapter } from '@/features/workspace/adapter';

import { eventsSections, stabilitySections, type Stability, type StabilityEvents } from './hypercareModel';
import { HypercareActions } from './HypercareActions';

export const stabilityAdapter: LineAdapter<Stability> = {
  key: 'stability',
  read: (ref) => readPanel<Stability>(ref),
  sections: (s) => stabilitySections(s),
  Actions: HypercareActions,
};

export const eventsAdapter: LineAdapter<StabilityEvents> = {
  key: 'stability/events',
  read: (ref) => readPanel<StabilityEvents>(ref),
  sections: (e) => eventsSections(e),
};

registerLineAdapter(stabilityAdapter as LineAdapter);
registerLineAdapter(eventsAdapter as LineAdapter);
