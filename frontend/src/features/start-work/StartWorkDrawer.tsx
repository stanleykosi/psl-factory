'use client';

// CMP-23 drawer: reads E-LINES on every opening, then shows the chooser or a line's drawer. The main button opens
// E-LINES `default_line` directly; without one (CEO and CTO, D-LEADERS-START), and from the chevron or "+ Start",
// the chooser opens first. A start that answers 201 closes the drawer and goes to the new work item.
import { usePathname, useRouter } from 'next/navigation';
import { useCallback, useState } from 'react';

import { Callout, Loading } from '@/components';

import { DrawerFrame } from './DrawerFrame';
import { LineChooser } from './LineChooser';
import { LineForm } from './LineForm';
import type { Line } from './types';
import { useLines } from './useStartWork';

import './start-work.css';

export type StartEntry = 'default' | 'chooser';

type Step = { kind: 'entry' } | { kind: 'chooser' } | { kind: 'line'; line: Line };

export function StartWorkDrawer({ entry, onClose, prefill, onStarted: started, onConflict }: {
  entry: StartEntry;
  onClose: () => void;
  /** The assistant's draft: opens this line's form directly, filled for the person to check. */
  prefill?: { line_key: string; intake: Record<string, unknown> };
  /** Replaces the default (close and go to the new work item). */
  onStarted?: (workId: string) => void;
  /** Called when a start answers 409 (the record changed or was started elsewhere), so the caller can read it again. */
  onConflict?: () => void;
}) {
  const router = useRouter();
  const pathname = usePathname() ?? '/';
  const { state, reload } = useLines();
  const [step, setStep] = useState<Step>({ kind: 'entry' });

  const onStarted = useCallback(
    (workId: string) => {
      if (started) return started(workId);
      onClose();
      router.push(`/work/${encodeURIComponent(workId)}`);
    },
    [onClose, router, started],
  );

  let view: Step = step;
  if (step.kind === 'entry') {
    const data = state.status === 'ready' ? state.data : undefined;
    const wanted = prefill ? prefill.line_key : entry === 'default' ? data?.default_line : undefined;
    const direct = wanted ? data?.items.find((l) => l.key === wanted) : undefined;
    if (direct) view = { kind: 'line', line: direct };
    else if (prefill && data) {
      // The draft names a line this person can't start: no form.
      return (
        <DrawerFrame eyebrow="START WORK" title="Start work" onClose={onClose} focusKey="not-here">
          <Callout kind="problem">
            <strong>You can’t start this here.</strong>
          </Callout>
        </DrawerFrame>
      );
    } else if ((entry === 'default' || prefill) && state.status === 'loading') {
      return (
        <DrawerFrame eyebrow="START WORK" title="Start work" onClose={onClose} focusKey="entry-loading">
          <Loading>Loading…</Loading>
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
        onConflict={onConflict}
        initialIntake={prefill?.line_key === view.line.key ? prefill.intake : undefined}
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
