'use client';

// The composer for one agent, with the mention picker, the held microphone, and the notes under it (a conflict
// re-read, "Try again" after an uncertain send). The state is the caller's `useSend`.
import { Button, Composer, AGENTS } from '@/components';
import { SignedOutState } from '@/shell/FrameStates';

import { chipKey, chipLabel, type useSend } from './useSend';
import { PLACEHOLDER } from './labels';
import { MentionPicker } from './MentionPicker';
import type { AgentName } from './types';

export function ComposerBar({ agent, send, pathname }: { agent: AgentName; send: ReturnType<typeof useSend>; pathname: string }) {
  if (send.signedOut) return <SignedOutState pathname={pathname} />;
  return (
    <div className="as__composer">
      <Composer
        agentName={AGENTS[agent].name}
        value={send.text}
        onChange={send.setText}
        onSend={() => void send.send()}
        canSend={send.canSend}
        busy={send.busy}
        placeholder={PLACEHOLDER[agent]}
        error={
          send.error && (
            <>
              {send.error}
              {send.unsure && (
                <>
                  {' '}
                  <Button kind="secondary" size="sm" onClick={() => void send.send()} disabled={!send.canSend}>
                    Try again
                  </Button>
                </>
              )}
            </>
          )
        }
        chips={send.chips.map((chip) => ({ id: chipKey(chip), label: chipLabel(chip) }))}
        onRemoveChip={send.removeChip}
        toolbar={<MentionPicker onPick={send.addChip} />}
        images={send.images}
        onAttach={send.attach}
        onRemoveImage={send.removeImage}
        heldMic
      />
      {send.notice && (
        <p className="psl-hint" role="status">
          {send.notice}
        </p>
      )}
    </div>
  );
}
