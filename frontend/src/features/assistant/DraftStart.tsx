'use client';

// A draft in the thread. Its start button opens the normal Start work drawer, prefilled from `draft.start`; the person
// checks the values and presses the drawer's own button, so the work item is theirs. The agent never starts, approves,
// sends or pays. Once `draft.started` is read, the button goes and the started line takes its place.
import { useEffect, useRef, useState } from 'react';

import { Button, DraftCard, Link, Money, Unknown, useIsPhone, type DraftRow } from '@/components';
import { StartWorkDrawer } from '@/features/start-work/StartWorkDrawer';

import { workHref } from './model';
import type { Draft } from './types';

type Row = Draft['rows'][number];

function rowValue(row: Row) {
  const money = row.money;
  if (!money) return row.value ?? '';
  const amount =
    money.unknown || money.amount === undefined ? (
      <Unknown />
    ) : money.currency === 'NGN' ? (
      <Money value={money.amount} />
    ) : (
      <span className="psl-mono">
        {money.currency} {money.amount}
      </span>
    );
  return row.value ? (
    <>
      {amount} {row.value}
    </>
  ) : (
    amount
  );
}

export function DraftStart({ draft, reread }: {
  draft: Draft;
  /** Reads the conversation again after the start. */
  reread: () => Promise<unknown>;
}) {
  const phone = useIsPhone();
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const startedLine = useRef<HTMLParagraphElement>(null);
  // Set when the drawer has just ended: focus goes to the started line if the next read shows one.
  const justStarted = useRef(false);
  const { start, started } = draft;

  // The drawer closed: focus goes back to the button that opened it (a press does not always focus it, as on touch).
  const wasOpen = useRef(false);
  useEffect(() => {
    if (wasOpen.current && !open) button.current?.focus();
    wasOpen.current = open;
  }, [open]);

  useEffect(() => {
    if (started && justStarted.current) {
      justStarted.current = false;
      startedLine.current?.focus();
    }
  }, [started]);

  // Either way the drawer ends, the thread is read again: it shows the started line (this start, or one made in another
  // tab) and the button goes. Focus follows to the started line if it appears.
  const closed = () => {
    justStarted.current = true;
    setOpen(false);
    void reread();
  };

  const rows: DraftRow[] = draft.rows.map((row) => ({ label: row.label, value: rowValue(row) }));
  return (
    <>
      <DraftCard
        title={draft.title}
        status={draft.status_label}
        rows={rows}
        next={draft.next}
        action={
          start && !started ? (
            <Button ref={button} kind="start" size={phone ? 'lg' : 'md'} block={phone} aria-haspopup="dialog" onClick={() => setOpen(true)}>
              {start.label}
            </Button>
          ) : undefined
        }
        started={
          started ? (
            <>
              Started{started.reference ? ` ${started.reference}` : ''}. <Link href={workHref(started.work_id)}>Open the work item</Link>
            </>
          ) : undefined
        }
        startedRef={startedLine}
      />
      {open && start && (
        <StartWorkDrawer
          entry="default"
          prefill={{ line_key: start.line_key, intake: start.intake ?? {} }}
          onClose={closed}
          onStarted={closed}
        />
      )}
    </>
  );
}
