'use client';

// F-112: the change page's own controls (the adapter's `Actions` slot): record a team's assessment, record a decision and record the
// authorisation. Which of them is drawn is the read's answer (`assessors`, each row's `verdicts`, `can_authorize`); the page has no rule
// about who may act. Sending, locking and error words are useWorkCommand's. Every press is one request, nothing is sent again by itself, and
// no word of "recorded", "approved" or "authorised" is drawn here: the sections say what the re-read shows. After an accepted write the
// controls stay off until a new read lands, so the next write never uses the old revisions.
import { useState } from 'react';

import { Button, Callout, Dialog, Select, TextArea, type SelectOption } from '@/components';
import type { LineActionsProps } from '@/features/workspace/adapter';
import { useWorkCommand } from '@/features/workspace/useWorkCommand';

import { AssessForm } from './AssessForm';
import { authorizeInputs, authorizeOffered, decideHeld, decideInputs, IDS, NOTE_LIMIT, proofLabel, TEXT, type Change, type Decider, type Readback, type Verdict } from './changeModel';

const VERDICT_WORDS: Record<Verdict, string> = { approve: 'Approve', return: 'Return', reject: 'Reject' };
/** Return and reject ask for one more confirmation before they are sent. */
const CONFIRMED: Verdict[] = ['return', 'reject'];
type Draft = { note: string; evidence: string | undefined };
const NO_DRAFT: Draft = { note: '', evidence: undefined };

type Confirm = { kind: 'decide'; role: Decider['role']; verdict: Verdict } | { kind: 'authorize' };

export function ChangeActions({ readback, ctx, commands, reload, onAccessLost }: LineActionsProps<Readback>) {
  const send = useWorkCommand({ item: ctx, reload, onAccessLost });
  const c: Change = readback.change;
  const byId = (id: string) => commands.find((x) => x.id === id);
  // the read an accepted write came from: nothing is sent from it again; a new read replaces it
  const [spent, setSpent] = useState<Change | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [commercial, setCommercial] = useState<string | undefined>();
  const [confirm, setConfirm] = useState<Confirm | null>(null);

  const locked = IDS.some((id) => send.lockedReason(id) !== null);
  const blocked = (id: string) => send.lockedReason(id) ?? (locked ? TEXT.locked : null) ?? (spent === c ? TEXT.reading : null);
  const run = async (id: string, inputs: Record<string, unknown>) => {
    const command = byId(id);
    if (!command) return false;
    const outcome = await send.run(command, inputs);
    if (outcome === 'sent') setSpent(c);
    return outcome === 'sent';
  };

  const assess = byId('change.assess');
  const decide = byId('change.decide');
  const authorize = byId('change.authorize');
  const draftOf = (role: string) => drafts[role] ?? NO_DRAFT;
  const setDraft = (role: string, patch: Partial<Draft>) => setDrafts((d) => ({ ...d, [role]: { ...(d[role] ?? NO_DRAFT), ...patch } }));
  const proofs: SelectOption[] = c.evidence.map((p) => ({ value: String(p.id), label: proofLabel(p) }));

  // a row with no verdicts is drawn only when a note typed for it is still unsent (a decision recorded by someone else meanwhile)
  const rows = c.decisions.filter((d) => d.verdicts.length > 0 || draftOf(d.role).note.trim() !== '');

  const sendDecision = (role: Decider['role'], verdict: Verdict) => {
    const d = draftOf(role);
    const choice = { role, verdict, note: d.note, evidence: d.evidence };
    if (decideHeld(c, choice) !== null) return;
    void run('change.decide', decideInputs(choice)).then((accepted) => {
      if (accepted) setDrafts((all) => ({ ...all, [role]: NO_DRAFT }));
    });
  };
  const pendingDecision = confirm?.kind === 'decide' ? confirm : null;
  const choices: SelectOption[] = c.authorization_choices.map((id) => ({ value: String(id), label: `Commercial item #${id}` }));
  const notice = send.notice;

  return (
    <div className="wr-actions">
      {c.assessors.map((team) => (
        <AssessForm
          key={team}
          team={team}
          change={c}
          command={assess}
          blocked={assess ? blocked(assess.id) : null}
          busy={send.busy}
          pending={send.pending === 'change.assess'}
          send={(inputs) => run('change.assess', inputs)}
        />
      ))}

      {rows.length > 0 && decide && (
        <section className="wr-block" aria-label="Record a decision">
          <h3 className="wr-head">Record a decision</h3>
          {rows.map((row) => {
            const d = draftOf(row.role);
            return (
              <div key={row.role} className="wr-block" role="group" aria-label={`${row.role} decision`}>
                <h4 className="wr-sub">{row.role}</h4>
                {row.verdicts.length === 0 ? (
                  <>
                    <p className="wr-line">This decision is no longer open to you. Your note was not sent:</p>
                    <p className="wr-text">{d.note}</p>
                  </>
                ) : (
                  <>
                    {proofs.length === 0 ? <p className="wr-line">{TEXT.noProof}</p> : <Select label={`${row.role} proof`} placeholder="Choose the proof" options={proofs} value={d.evidence} onChange={(evidence) => setDraft(row.role, { evidence })} />}
                    <TextArea label={`${row.role} note`} limit={NOTE_LIMIT} value={d.note} onChange={(e) => setDraft(row.role, { note: e.target.value })} />
                    <div className="wr-buttons">
                      {row.verdicts.map((verdict) => {
                        const reason = decide.disabledReason ?? blocked(decide.id) ?? decideHeld(c, { role: row.role, verdict, note: d.note, evidence: d.evidence });
                        return (
                          <Button
                            key={verdict}
                            kind={verdict === 'approve' ? 'primary' : verdict === 'reject' ? 'reject' : 'secondary'}
                            disabled={send.busy || reason !== null}
                            busy={send.pending === decide.id}
                            busyLabel="Working…"
                            reason={reason}
                            aria-label={`${VERDICT_WORDS[verdict]} for ${row.role}`}
                            onClick={() => (CONFIRMED.includes(verdict) ? setConfirm({ kind: 'decide', role: row.role, verdict }) : sendDecision(row.role, verdict))}
                          >
                            {VERDICT_WORDS[verdict]}
                          </Button>
                        );
                      })}
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </section>
      )}

      {authorize && authorizeOffered(c) && (
        <section className="wr-block" aria-label="Record the authorisation">
          <h3 className="wr-head">Record the authorisation</h3>
          {choices.length > 0 && <Select label="Linked commercial item" optional placeholder="None" options={choices} value={commercial} onChange={setCommercial} />}
          <div className="wr-buttons">
            {(() => {
              const reason = authorize.disabledReason ?? blocked(authorize.id);
              return (
                <Button disabled={send.busy || reason !== null} busy={send.pending === authorize.id} busyLabel="Working…" reason={reason} onClick={() => setConfirm({ kind: 'authorize' })}>
                  Record authorisation
                </Button>
              );
            })()}
          </div>
        </section>
      )}

      {notice?.kind === 'error' && (
        <Callout kind="problem">
          {notice.text}
          {notice.detail && <> {notice.detail}</>}
        </Callout>
      )}

      {pendingDecision && (
        <Dialog
          title={`${VERDICT_WORDS[pendingDecision.verdict]} for ${pendingDecision.role}`}
          actionLabel={VERDICT_WORDS[pendingDecision.verdict]}
          destructive={pendingDecision.verdict === 'reject'}
          onCancel={() => setConfirm(null)}
          onAction={() => {
            setConfirm(null);
            sendDecision(pendingDecision.role, pendingDecision.verdict);
          }}
        >
          <p>Your note goes with it:</p>
          <p className="wr-text">{draftOf(pendingDecision.role).note}</p>
        </Dialog>
      )}
      {confirm?.kind === 'authorize' && (
        <Dialog
          title="Record the authorisation"
          actionLabel="Record authorisation"
          onCancel={() => setConfirm(null)}
          onAction={() => {
            setConfirm(null);
            void run('change.authorize', authorizeInputs(c, commercial));
          }}
        >
          <p>{TEXT.authoriseCommits}</p>
          <p>{commercial !== undefined && c.authorization_choices.some((id) => String(id) === commercial) ? `Linked commercial item: #${commercial}.` : 'No commercial item is linked.'}</p>
        </Dialog>
      )}
    </div>
  );
}
