'use client';

// The demo bar (D-155): a small tool for the design engineer when the app runs against the mock in the live demo. It
// switches the role (the mock's psl_mock_persona cookie), sets the answer speed (psl_mock_speed) and resets the demo's
// in-memory state. It exists only when the dev script sets NEXT_PUBLIC_MOCK_DEMO=1; a production build never renders it.
import { useState } from 'react';

import { Button, Segmented, Select } from '@/components';

import './demo-bar.css';

const ENABLED = process.env.NODE_ENV !== 'production' && process.env.NEXT_PUBLIC_MOCK_DEMO === '1';

const ROLES = [
  { value: 'finance_lead', label: 'Finance Lead' },
  { value: 'pm', label: 'PM' },
  { value: 'pmo_lead', label: 'PMO Lead' },
  { value: 'ceo', label: 'CEO' },
  { value: 'hr', label: 'HR' },
  { value: 'hr_lead', label: 'HR Lead' },
  { value: 'admin', label: 'Admin' },
  { value: 'none', label: 'No access' },
];
const SPEEDS = [
  { value: 'fast', label: 'Fast' },
  { value: 'normal', label: 'Normal' },
  { value: 'slow', label: 'Slow' },
] as const;
type Speed = (typeof SPEEDS)[number]['value'];

function readCookie(name: string): string | undefined {
  const pair = document.cookie.split('; ').find((part) => part.startsWith(`${name}=`));
  return pair ? decodeURIComponent(pair.slice(name.length + 1)) : undefined;
}
const writeCookie = (name: string, value: string) => {
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; SameSite=Lax`;
};

export function DemoBar() {
  const [open, setOpen] = useState(false);
  const [role, setRole] = useState('finance_lead');
  const [speed, setSpeed] = useState<Speed>('normal');
  const [resetting, setResetting] = useState(false);
  if (!ENABLED) return null;

  function show() {
    const saved = readCookie('psl_mock_speed');
    setRole(readCookie('psl_mock_persona') ?? 'finance_lead');
    setSpeed(SPEEDS.some((s) => s.value === saved) ? (saved as Speed) : 'normal');
    setOpen(true);
  }

  function chooseRole(value: string) {
    writeCookie('psl_mock_persona', value);
    window.location.reload();
  }

  function chooseSpeed(value: Speed) {
    writeCookie('psl_mock_speed', value);
    setSpeed(value);
  }

  async function reset() {
    setResetting(true);
    try {
      await fetch('/__mock/reset', { method: 'POST' });
    } finally {
      window.location.reload();
    }
  }

  return (
    <aside className="demo-bar" aria-label="Demo controls">
      {open ? (
        <div className="demo-bar__panel">
          <div className="demo-bar__head">
            <strong>Demo</strong>
            <Button kind="link" onClick={() => setOpen(false)}>Hide</Button>
          </div>
          <Select label="Role" options={ROLES} value={role} onChange={chooseRole} placeholder="Choose a role" />
          <Segmented label="Speed" options={[...SPEEDS]} value={speed} onChange={chooseSpeed} />
          <Button kind="secondary" size="sm" busy={resetting} busyLabel="Resetting…" onClick={reset}>Reset demo</Button>
        </div>
      ) : (
        <Button kind="secondary" size="sm" onClick={show}>Demo</Button>
      )}
    </aside>
  );
}
