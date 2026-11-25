// The one place line adapters are registered. The work item page imports only this file; a line adds one import (or one
// registerLineAdapter call) here, in its own commit.
import { registerLineAdapter, type LineAdapter } from '../adapter';
import { bidAnswersAdapter } from '../bidAnswersAdapter';
import { weeklyReportAdapter } from '../weeklyReportAdapter';
import '@/features/issue-followup/issueFollowupAdapter'; // F-111 (lane D): self-registers on import
import '@/features/forecast/forecastAdapter'; // F-103 (lane D): self-registers on import

registerLineAdapter(weeklyReportAdapter as LineAdapter);
registerLineAdapter(bidAnswersAdapter as LineAdapter);
