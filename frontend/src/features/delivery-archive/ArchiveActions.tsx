'use client';

// F-116: the archive page's own controls (the adapter's `Actions` slot): start the archive from a reviewed source list, the files by group
// with "Look up" and "Copy again" on the files the read offers them for. Which control is drawn is the read's answer (`can_reserve`, each
// file's `actions`); the page has no rule about who may act. Sending, locking and error words are useWorkCommand's. The result is told from
// the re-read (the sections), never from the 200, so the only success text here is "Queued", which says the request was accepted.
// "Check what happened" is the work item's own control (listed by the item's `actions`), not drawn here.
import { useState } from 'react';

import { Button, Callout, Checkbox, Disclosure } from '@/components';
import type { CommandDescriptor, LineActionsProps } from '@/features/workspace/adapter';
import { useWorkCommand } from '@/features/workspace/useWorkCommand';

import { canLookup, canRetry, chosenSources, defaultSources, filesToCheck, groupsOf, receiptLabel, sourceLabel, startHeld, STATE_WORDS, stateOf, TEXT, type Archive, type ArchiveFile } from './archiveModel';

export function ArchiveActions({ readback: a, ctx, commands, reload, onAccessLost }: LineActionsProps<Archive>) {
  const send = useWorkCommand({ item: ctx, reload, onAccessLost });
  const [picked, setPicked] = useState<number[] | null>(null);
  const [queued, setQueued] = useState(false);
  const byId = (id: string) => commands.find((c) => c.id === id);
  const sources = picked ?? defaultSources(a);
  // a write that may have happened locks every archive control until the page is re-read
  const locked = commands.some((c) => send.lockedReason(c.id) !== null);

  const reasonFor = (c: CommandDescriptor, held: string | null) => c.disabledReason ?? send.lockedReason(c.id) ?? (locked ? TEXT.locked : null) ?? held;
  const press = (c: CommandDescriptor, label: string, held: string | null, onPress: () => void, kind: 'primary' | 'secondary' = 'secondary') => {
    const reason = reasonFor(c, held);
    return (
      <Button key={c.id} kind={kind} size="sm" disabled={send.busy || reason !== null} busy={send.pending === c.id} busyLabel="Working…" reason={reason} onClick={onPress}>
        {label}
      </Button>
    );
  };

  const start = byId('archive.reserve');
  const startNow = async () => {
    if (!start) return;
    setQueued(false);
    if ((await send.run(start, { source_ids: chosenSources(a, sources) })) === 'sent') setQueued(true);
  };
  const toggle = (id: number) => setPicked(sources.includes(id) ? sources.filter((s) => s !== id) : [...sources, id]);

  const check = (f: ArchiveFile) => {
    if (f.job === null) return null;
    const lookup = canLookup(f) ? byId(`archive.lookup.${f.job.id}`) : undefined;
    const retry = canRetry(f) ? byId(`archive.retry.${f.job.id}`) : undefined;
    if (!lookup && !retry) return null;
    return (
      <div className="wr-buttons">
        {lookup && press(lookup, 'Look up', null, () => void send.run(lookup))}
        {retry && press(retry, 'Copy again', null, () => void send.run(retry))}
      </div>
    );
  };

  const toCheck = filesToCheck(a).length;
  const notice = send.notice;
  return (
    <div className="wr-actions">
      {a.can_reserve && start && (
        <section className="wr-block" aria-label="Start the archive">
          <h3 className="wr-head">Start the archive</h3>
          <p className="wr-line">{TEXT.review}</p>
          {a.sources.map((s) => (
            <Checkbox key={s.id} label={s.label} checked={sources.includes(s.id)} disabled={send.busy} onChange={() => toggle(s.id)} />
          ))}
          <div className="wr-buttons">{press(start, 'Start archive', startHeld(a, sources), () => void startNow(), 'primary')}</div>
        </section>
      )}
      {queued && <p className="wr-line" role="status">{TEXT.queued}</p>}
      {a.files.length > 0 && (
        <section className="wr-block" aria-label="Archive files">
          <h3 className="wr-head">Files</h3>
          {toCheck > 0 && <p className="wr-line">{TEXT.checkIntro}</p>}
          {groupsOf(a).map((g) => (
            <Disclosure key={g.name} summary={`${g.name} · ${g.files.length} ${g.files.length === 1 ? 'file' : 'files'} · ${g.state}`} defaultOpen={g.files.some((f) => f.job?.state === 'unknown' || f.job?.state === 'missing')}>
              {g.files.map((f) => (
                <div key={f.id} className="wr-block">
                  <p className="wr-text">{f.name}</p>
                  <p className="wr-line">
                    {[f.status, STATE_WORDS[stateOf(f)], sourceLabel(f), receiptLabel(f)].filter((x) => x !== null && x !== '').join(' · ')}
                  </p>
                  {check(f)}
                </div>
              ))}
            </Disclosure>
          ))}
        </section>
      )}
      {notice?.kind === 'error' && (
        <Callout kind="problem">
          {notice.text}
          {notice.detail && <> {notice.detail}</>}
        </Callout>
      )}
    </div>
  );
}
