'use client';

import { Button } from '@/components';

type Props = { name: string; on: boolean; onToggle: () => void; describedBy?: string };

/** An on/off switch drawn as on SCR-15 settings. A native button, so Space and Enter toggle. */
export function AlertSwitch({ name, on, onToggle, describedBy }: Props) {
  return (
    <Button kind="bare" role="switch" aria-checked={on} aria-label={name} aria-describedby={describedBy} className={`alerts-switch${on ? ' is-on' : ''}`} onClick={onToggle}>
      <span className="alerts-switch__knob" aria-hidden="true" />
    </Button>
  );
}
