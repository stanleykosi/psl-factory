'use client';

type Props = { name: string; on: boolean; locked: boolean; onToggle: () => void };

/** An on/off switch drawn as on SCR-15 settings. A native button, so Space and Enter toggle; locked never toggles. */
export function AlertSwitch({ name, on, locked, onToggle }: Props) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={name}
      aria-disabled={locked || undefined}
      className={`alerts-switch${on ? ' is-on' : ''}${locked ? ' is-locked' : ''}`}
      onClick={() => {
        if (!locked) onToggle();
      }}
    >
      <span className="alerts-switch__knob" aria-hidden="true" />
    </button>
  );
}
