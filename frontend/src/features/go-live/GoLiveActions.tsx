'use client';

// F-114: the go-live page's own controls (the adapter's `Actions` slot): record the signatures, prepare v2 after a request for changes
// and the decline panel. Which of them is drawn is the reads' answer; the page has no rule about who may sign. Sending, locking and error
// words are useWorkCommand's. The result is told from the re-read (the sections), never from the 200, so no success text is drawn here.
import { Callout } from '@/components';
import type { LineActionsProps } from '@/features/workspace/adapter';
import { useWorkCommand } from '@/features/workspace/useWorkCommand';

import { DeclinePanel, SuccessorForm } from './DeclinePanel';
import { declineReplies, showSignoff, showSuccessor, type Readback } from './goLiveModel';
import { SignoffForm } from './SignoffForm';

export function GoLiveActions({ readback, ctx, commands, reload, onAccessLost }: LineActionsProps<Readback>) {
  const send = useWorkCommand({ item: ctx, reload, onAccessLost });
  const { signoff, replies, decline } = readback;
  const notice = send.notice;
  return (
    <div className="wr-actions">
      {signoff && showSignoff(readback) && <SignoffForm s={signoff} caseId={ctx.caseId} send={send} commands={commands} />}
      {showSuccessor(replies) && <SuccessorForm send={send} command={commands.find((c) => c.id === 'go-live.successor')} />}
      {decline && <DeclinePanel replies={declineReplies(readback)} d={decline} send={send} commands={commands} />}
      {notice?.kind === 'error' && (
        <Callout kind="problem">
          {notice.text}
          {notice.detail && <> {notice.detail}</>}
        </Callout>
      )}
    </div>
  );
}
