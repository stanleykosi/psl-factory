'use client';

// F-114: the controls after the client's reply: Prepare v2 (after changes) and, for a declined reply, link an issue and prepare a new
// release candidate. Each is drawn only for the reply the decline read supplies options for; every choice is from that read's lists.
// "Review the remediation" and recording the reply itself need a proof file no read supplies, so they are not drawn (TEXT.remediationHeld).
import { useState } from 'react';

import { Select, TextArea, TextField, type SelectOption } from '@/components';
import type { CommandDescriptor } from '@/features/workspace/adapter';

import { candidateHeld, candidateInputs, FIELD_LIMIT, issueHeld, issueInputs, NEW_ISSUE, NEXT_ACTION_LIMIT, NOTE_LIMIT, REASON_LIMIT, TEXT, TITLE_LIMIT, type Decline, type Reply } from './goLiveModel';
import { Press, type Send } from './Press';

export function SuccessorForm({ send, command }: { send: Send; command: CommandDescriptor | undefined }) {
  const [reason, setReason] = useState('');
  if (!command) return null;
  const held = reason.trim() === '' ? 'Say why a new version is needed.' : null;
  return (
    <section className="wr-block" aria-label="Prepare v2">
      <h3 className="wr-head">Prepare v2</h3>
      <TextArea label="Why a new version is needed" limit={REASON_LIMIT} value={reason} onChange={(ev) => setReason(ev.target.value)} />
      <div className="wr-buttons">
        <Press send={send} command={command} label="Prepare v2" held={held} onPress={() => held === null && void send.run(command, { reason: reason.trim() })} />
      </div>
    </section>
  );
}

function IssueForm({ reply, d, send, command }: { reply: Reply; d: Decline; send: Send; command: CommandDescriptor | undefined }) {
  const entry = d.issues.find((i) => i.reply_id === reply.id);
  const [issue, setIssue] = useState<string | undefined>();
  const [title, setTitle] = useState('');
  const [owner, setOwner] = useState<string | undefined>();
  const [nextAction, setNextAction] = useState('');
  const [note, setNote] = useState('');
  if (!entry || !command) return null;
  const choice = { replyId: reply.id, issue, title, owner, nextAction, note };
  const held = issueHeld(d, choice);
  const options: SelectOption[] = [...entry.existing_issues.map((i) => ({ value: String(i.id), label: i.label })), { value: NEW_ISSUE, label: 'Create a new issue' }];
  const owners: SelectOption[] = entry.owners.map((o) => ({ value: String(o.id), label: o.label }));
  return (
    <section className="wr-block" aria-label={`Link an issue to reply ${reply.number}`}>
      <h3 className="wr-head">Link an issue to this decline</h3>
      <Select label="Issue" placeholder="Choose an issue" options={options} value={issue} onChange={setIssue} />
      {issue === NEW_ISSUE && (
        <>
          <TextField label="Issue title" value={title} maxLength={TITLE_LIMIT} onChange={(ev) => setTitle(ev.target.value)} />
          <Select label="Owner" placeholder="Choose an owner" options={owners} value={owner} onChange={setOwner} />
          <TextArea label="Next action" optional limit={NEXT_ACTION_LIMIT} value={nextAction} onChange={(ev) => setNextAction(ev.target.value)} />
        </>
      )}
      <TextArea label="Note on the issue" limit={NOTE_LIMIT} value={note} onChange={(ev) => setNote(ev.target.value)} />
      <div className="wr-buttons">
        <Press send={send} command={command} label="Link the issue" held={held} onPress={() => held === null && void send.run(command, issueInputs(choice))} />
      </div>
    </section>
  );
}

function CandidateForm({ reply, d, send, command }: { reply: Reply; d: Decline; send: Send; command: CommandDescriptor | undefined }) {
  const [reference, setReference] = useState('');
  const [note, setNote] = useState('');
  if (!command || !d.new_candidates.some((n) => n.reply_id === reply.id)) return null;
  const choice = { replyId: reply.id, reference, note };
  const held = candidateHeld(d, choice);
  return (
    <section className="wr-block" aria-label={`Prepare a new release candidate for reply ${reply.number}`}>
      <h3 className="wr-head">Prepare a new release candidate</h3>
      <TextField label="Candidate reference" value={reference} maxLength={FIELD_LIMIT} onChange={(ev) => setReference(ev.target.value)} />
      <TextArea label="Note on the candidate" limit={NOTE_LIMIT} value={note} onChange={(ev) => setNote(ev.target.value)} />
      <div className="wr-buttons">
        <Press send={send} command={command} label="Prepare a new release candidate" held={held} onPress={() => held === null && void send.run(command, candidateInputs(d, choice))} />
      </div>
    </section>
  );
}

export function DeclinePanel({ replies, d, send, commands }: { replies: Reply[]; d: Decline; send: Send; commands: CommandDescriptor[] }) {
  const by = (id: string) => commands.find((c) => c.id === id);
  return (
    <>
      {replies.map((reply) => (
        <div key={reply.id} className="wr-block">
          <IssueForm reply={reply} d={d} send={send} command={by('go-live.link_decline_issue')} />
          <CandidateForm reply={reply} d={d} send={send} command={by('go-live.prepare_new_candidate')} />
          {d.review_options.some((o) => o.reply_id === reply.id) && <p className="wr-line">{TEXT.remediationHeld}</p>}
        </div>
      ))}
    </>
  );
}
