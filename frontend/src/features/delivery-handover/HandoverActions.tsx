'use client';

// F-117: the handover page's own controls (the adapter's `Actions` slot): Publish to Support, Record Support's reply and Support's own
// acknowledgement. Which of them is drawn is the reads' answer; the page has no rule about who may act, and a control the read does
// not offer is absent (no disabled button, no invented reason). Sending, locking and error words are useWorkCommand's. The result is
// told from the re-read (the sections), never from the 200, 201 or 202, so no success text is drawn here.
import { useState } from 'react';

import { Callout } from '@/components';
import type { LineActionsProps } from '@/features/workspace/adapter';
import { useWorkCommand } from '@/features/workspace/useWorkCommand';

import { AckForm, ReplyForm } from './HandoverForms';
import { TEXT, type Readback } from './handoverModel';
import { Press } from './Press';

export function HandoverActions({ readback, ctx, commands, reload, onAccessLost }: LineActionsProps<Readback>) {
  const send = useWorkCommand({ item: ctx, reload, onAccessLost });
  const publish = commands.find((c) => c.id === 'handover.publish');
  const record = commands.find((c) => c.id === 'handover.record_reply');
  const acknowledge = commands.find((c) => c.id === 'handover.acknowledge');
  const [closed, setClosed] = useState(false);
  const notice = send.notice;
  return (
    <div className="wr-actions">
      {publish && (
        <section className="wr-block" aria-label="Publish to Support">
          <h3 className="wr-head">Next</h3>
          <p className="wr-line">{TEXT.consequence}</p>
          <div className="wr-buttons">
            <Press send={send} command={publish} label="Publish to Support" held={null} onPress={() => void send.run(publish)} />
          </div>
        </section>
      )}
      {record && readback.replies && <ReplyForm replies={readback.replies} send={send} command={record} closed={closed} onClosed={setClosed} />}
      {acknowledge && readback.receipt && <AckForm receipt={readback.receipt} send={send} command={acknowledge} />}
      {notice?.kind === 'error' && (
        <Callout kind="problem">
          {notice.text}
          {notice.detail && <> {notice.detail}</>}
        </Callout>
      )}
    </div>
  );
}
