'use client';

// CMP-23 drawer: reads `GET /lines` on every opening, then shows the chooser or a line's drawer. The live contract has no
// default line, so every entry (the main button, the chevron, "+ Start") opens the chooser. `prefill` opens a form
// only for a line this person can start here. A start that answers 200 closes the drawer and goes to the new work item.
import { usePathname, useRouter } from 'next/navigation';
import { useCallback, useState } from 'react';

import { Callout, Loading } from '@/components';

import { DrawerFrame } from './DrawerFrame';
import { isStartable, LineChooser } from './LineChooser';
import { LineDrawer } from './LineForm';
import { lineFormFor, ownLineFor } from './lines';
import type { Line } from './types';
import { useLines } from './useStartWork';

import './start-work.css';

export type StartEntry = 'default' | 'chooser';

type Step = { kind: 'entry' } | { kind: 'chooser' } | { kind: 'line'; line: Line };

export function StartWorkDrawer({ onClose, prefill, onStarted: started, onConflict }: {
  /** Every entry opens the chooser; kept so callers need not change. */
  entry?: StartEntry;
  onClose: () => void;
  /** The assistant's draft: opens this line's form directly, when it is one this person can start here. */
  prefill?: { line_key: string; intake: Record<string, unknown> };
  /** Replaces the default (close and go to the new work item). */
  onStarted?: (workId: string) => void;
  /** Called when a start answers 409 (the record changed), so the caller can read it again. */
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
    const direct = prefill ? data?.items.find((l) => l.key === prefill.line_key && isStartable(l)) : undefined;
    if (direct) view = { kind: 'line', line: direct };
    else if (prefill && data) {
      // The draft names a line this person can't start here: no form.
      return (
        <DrawerFrame eyebrow="START WORK" title="Start work" onClose={onClose} focusKey="not-here">
          <Callout kind="problem">
            <strong>You can’t start this here.</strong>
          </Callout>
        </DrawerFrame>
      );
    } else if (prefill && state.status === 'loading') {
      return (
        <DrawerFrame eyebrow="START WORK" title="Start work" onClose={onClose} focusKey="entry-loading">
          <Loading>Loading…</Loading>
        </DrawerFrame>
      );
    } else view = { kind: 'chooser' };
  }

  const own = view.kind === 'line' ? ownLineFor(view.line.key) : undefined;
  if (view.kind === 'line' && own) {
    return <own.Own key={own.key} onBack={() => setStep({ kind: 'chooser' })} onClose={onClose} pathname={pathname} />;
  }
  const form = view.kind === 'line' ? lineFormFor(view.line.key) : undefined;
  if (view.kind === 'line' && form) {
    return (
      <LineDrawer
        key={view.line.key}
        form={form}
        line={view.line}
        lineKey={view.line.key}
        onBack={() => setStep({ kind: 'chooser' })}
        onClose={onClose}
        onStarted={onStarted}
        pathname={pathname}
        onConflict={onConflict}
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
