'use client';

// A Setup tab whose screen comes in a later feature (F-11B to F-11F): the frame with that tab current, no badges
// (no read is made here; Assumption A-9), and the shared empty pattern.
import { SETUP_TABS, SetupFrame, SetupGate, type SetupTab } from './SetupFrame';

export function ReservedTab({ tab }: { tab: Exclude<SetupTab, 'rules'> }) {
  const label = SETUP_TABS.find((t) => t.key === tab)!.label;
  return (
    <SetupGate>
      <div className="setup-page">
        <SetupFrame current={tab} />
        <div className="psl-empty">
          <h2>{label} comes next.</h2>
          <p>This part of Setup arrives in a later release.</p>
        </div>
      </div>
    </SetupGate>
  );
}
