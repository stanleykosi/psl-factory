'use client';

// A Setup tab whose screen comes in a later feature (F-11B to F-11F): the shared empty pattern under the frame the
// Setup layout draws. No read is made here, so the page tells the frame it is ready (Assumption A-9).
import { SETUP_TABS, useSetupRead, type SetupTab } from './SetupFrame';

export function ReservedTab({ tab }: { tab: Exclude<SetupTab, 'rules'> }) {
  const label = SETUP_TABS.find((t) => t.key === tab)!.label;
  useSetupRead('ready');
  return (
    <div className="setup-page">
      <div className="psl-empty">
        <h2>{label} comes next.</h2>
        <p>This part of Setup arrives in a later release.</p>
      </div>
    </div>
  );
}
