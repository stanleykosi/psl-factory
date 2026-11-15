'use client';

// CMP-23 drawer: reads E-LINES on every opening, then shows the chooser or a line's drawer. The main button opens
// E-LINES `default_line` directly; without one (CEO and CTO, D-LEADERS-START), and from the chevron or "+ Start",
// the chooser opens first. A start that answers 201 closes the drawer and goes to the new work item.
import { usePathname, useRouter } from 'next/navigation';
import { useCallback, useState } from 'react';

import { DrawerFrame } from './DrawerFrame';
import { LineChooser } from './LineChooser';
import { LineForm } from './LineForm';
import type { Line } from './types';
import { useLines } from './useStartWork';

import './start-work.css';

export type StartEntry = 'default' | 'chooser';

type Step = { kind: 'entry' } | { kind: 'chooser' } | { kind: 'line'; line: Line };

export function StartWorkDrawer({ entry, onClose }: { entry: StartEntry; onClose: () => void }) {
  const router = useRouter();
  const pathname = usePathname() ?? '/';
  const { state, reload } = useLines();
  const [step, setStep] = useState<Step>({ kind: 'entry' });

  const onStarted = useCallback(
    (workId: string) => {
      onClose();
      router.push(`/work/${encodeURIComponent(workId)}`);
    },
    [onClose, router],
  );

  let view: Step = step;
  if (step.kind === 'entry') {
    const data = state.status === 'ready' ? state.data : undefined;
    const direct = entry === 'default' && data?.default_line ? data.items.find((l) => l.key === data.default_line) : undefined;
    if (direct) view = { kind: 'line', line: direct };
    else if (entry === 'default' && state.status === 'loading') {
      return (
        <DrawerFrame eyebrow="START WORK" title="Start work" onClose={onClose} focusKey="entry-loading">
          <span className="psl-loading" role="status">
            <span className="psl-busy" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            Loading…
          </span>
        </DrawerFrame>
      );
    } else view = { kind: 'chooser' };
  }

  if (view.kind === 'line') {
    return (
      <LineForm
        key={view.line.key}
        line={view.line}
        onBack={() => setStep({ kind: 'chooser' })}
        onClose={onClose}
        onStarted={onStarted}
        pathname={pathname}
      />
    );
  }
  return (
    <LineChooser
      state={state}
      onRetry={() => void reload()}
      onNext={(line) => setStep({ kind: 'line', line })}
      onClose={onClose}
      pathname={pathname}
    />
  );
}
