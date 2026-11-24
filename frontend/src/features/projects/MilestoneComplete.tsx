'use client';

// SCR-19 Mark a milestone complete (/projects/[caseId]/milestones/complete?name=): one named milestone, the proof on
// record (an existing proof, or a private PDF), a confirmation, and one "Mark complete". The control is drawn only when
// the options read says `can_complete` (the server decides; no role is checked here). "Recorded" is shown only after the
// re-read. Completing only queues the Finance handoff (D-187): this screen never starts, drafts or promises an invoice.
import Link from 'next/link';
import { useEffect, useRef } from 'react';

import { Breadcrumb, Button, buttonClass, Callout, Checkbox, PageTitle, Panel, RadioGroup, useIsPhone, When } from '@/components';
import { EvidencePicker } from '@/features/workspace/EvidencePicker';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { useMe, usePhoneBack } from '@/shell/AppShell';
import { hasDestination, visibleDestinations } from '@/shell/destinations';
import { LoadingState, NotOpenState, SignedOutState } from '@/shell/FrameStates';

import { holdText, usableName } from './milestonesModel';
import { routeCaseId, textOf } from './model';
import { useMilestoneComplete } from './useMilestoneComplete';
import { useProject } from './useProject';

import './milestone-complete.css';

const NEXT =
  'The milestone is recorded as complete, with the proof you chose. Finance is handed this milestone and starts any invoice itself. The amount comes from the contract, not from this form. Completing a milestone is not invoicing it. PMO completes milestones; Finance handles invoices.';
const NOTE_ID = 'mscomplete-why';

function NoAccess({ base }: { base: string }) {
  return (
    <section className="psl-panel mscomplete__card" aria-label="No access">
      <div className="psl-panel__body">
        <PageTitle>Mark a milestone complete</PageTitle>
        <p className="mscomplete__plain">This project or milestone isn&rsquo;t available to you.</p>
        <p className="mscomplete__plain">
          <Link className={buttonClass('dark', 'lg')} href={base}>
            Back to the project
          </Link>
        </p>
      </div>
    </section>
  );
}

function NextBlock() {
  return (
    <Panel head="What happens next" headingLevel={2} className="mscomplete__next">
      <p className="mscomplete__plain">{NEXT}</p>
    </Panel>
  );
}

function Recorded({ completion, base }: { completion: { name: string; completed_at: string; proof_version: number }; base: string }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), []);
  return (
    <div className="mscomplete__row">
      <Panel kind="default" head="Milestone recorded" headingLevel={2} className="mscomplete__card">
        <h3 ref={heading} tabIndex={-1} className="mscomplete__name">
          {completion.name}
        </h3>
        <p className="mscomplete__plain">
          Completed <When value={completion.completed_at} show="daytime" />
        </p>
        <p className="mscomplete__plain">Proof version {completion.proof_version}</p>
        <p className="mscomplete__plain">{NEXT}</p>
        <Link className={buttonClass('secondary', 'lg')} href={`${base}/milestones`}>
          Back to Milestones
        </Link>
      </Panel>
    </div>
  );
}

function Body({ caseId, name }: { caseId: string; name: string }) {
  const phone = useIsPhone();
  const project = useProject(caseId);
  const base = `/projects/${encodeURIComponent(caseId)}`;
  const pathname = `${base}/milestones/complete?name=${encodeURIComponent(name)}`;
  const title = project.state.status === 'ready' ? textOf(project.state.journey.title) : undefined;
  usePhoneBack({ label: 'Milestones', href: `${base}/milestones` });
  const m = useMilestoneComplete(caseId, name);
  const { read, submit, notes } = m;

  if (read.status === 'loading') return <LoadingState />;
  if (submit.status === 'signed_out') return <SignedOutState pathname={pathname} />;
  if (read.status === 'error') {
    const { error } = read;
    if (error.kind === 'unauthenticated') return <SignedOutState pathname={pathname} />;
    if (error.kind === 'forbidden' || error.kind === 'not_found') return <NoAccess base={base} />;
    return <WorkErrorCard message="We couldn’t load this milestone. Nothing was changed." error={error} onRetry={() => void m.retry()} />;
  }
  if (submit.status === 'no_access') return <NoAccess base={base} />;

  const { options } = read;
  const crumb = [{ label: title ?? 'Projects', href: title ? base : '/projects' }, { label: 'Milestones', href: `${base}/milestones` }];
  const header = (
    <header className="mscomplete__header">
      <Breadcrumb items={crumb} />
      <PageTitle size={36} phoneSize={24}>
        Mark a milestone complete
      </PageTitle>
    </header>
  );
  if (submit.status === 'recorded') {
    return (
      <div className="mscomplete">
        {header}
        <Recorded completion={submit.completion} base={base} />
      </div>
    );
  }

  const settled = submit.status === 'idle' || submit.status === 'refused';
  const locked = !settled;
  const hold = holdText(options);
  const usingPdf = m.chosen?.kind === 'pdf';
  const missing = [
    m.chosen === null && 'Choose the proof.',
    usingPdf && !m.fileChecked && 'Tick that you have checked the file.',
    !m.confirmed && 'Tick the confirmation.',
  ].filter((x): x is string => typeof x === 'string');
  const ready = missing.length === 0 && settled;
  const noProofs = options.proofs.length === 0 && !options.can_attach_pdf;

  const button = (
    <Button
      size="lg"
      block={phone}
      busy={submit.status === 'busy' || submit.status === 'confirming'}
      busyLabel="Marking complete…"
      disabled={!ready && submit.status !== 'busy' && submit.status !== 'confirming'}
      aria-describedby={!ready && settled ? NOTE_ID : undefined}
      onClick={() => void m.complete()}
    >
      Mark complete
    </Button>
  );

  return (
    <div className="mscomplete">
      {header}
      <div className="mscomplete__row">
        <Panel head="Milestone" headingLevel={2} className="mscomplete__card" aria-busy={submit.status === 'busy' || submit.status === 'confirming'}>
          <div className="mscomplete__fields">
            <div className="mscomplete__field">
              <span className="mscomplete__label">Milestone</span>
              <strong className="mscomplete__name">{name}</strong>
            </div>

            {notes.conflict && (
              <Callout kind="warning">This project changed while you were confirming. We reloaded it. Check the proof and press Mark complete again.</Callout>
            )}
            {notes.proofGone && <Callout kind="warning">That proof is no longer available.</Callout>}
            {notes.notRecorded && <Callout kind="info">It wasn&rsquo;t recorded. Your choices are kept; press Mark complete when you are ready.</Callout>}
            {submit.status === 'refused' && <Callout kind="problem">{submit.message}</Callout>}
            {hold && <Callout kind="warning">{hold}</Callout>}
            {options.hold === 'name_in_use' && (
              <p className="mscomplete__plain">
                <Link href={`${base}/milestones`}>Open the Milestones tab</Link>
              </p>
            )}

            {submit.status === 'confirming' && (
              <p role="status" className="mscomplete__plain">
                Checking the record…
              </p>
            )}
            {submit.status === 'unconfirmed' && (
              <Callout kind="warning">
                We saved your completion but couldn&rsquo;t confirm it yet. Check again.{' '}
                <Button kind="secondary" size="sm" busy={submit.checking} busyLabel="Checking…" onClick={() => void m.check()}>
                  Check again
                </Button>
              </Callout>
            )}
            {submit.status === 'uncertain' && (
              <Callout kind="warning">
                We couldn&rsquo;t tell whether this was recorded. Check before trying again.{' '}
                <Button kind="secondary" size="sm" busy={submit.checking} busyLabel="Checking…" onClick={() => void m.check()}>
                  Check again
                </Button>
              </Callout>
            )}
            {submit.status === 'now_recorded' && (
              <Callout kind="info">
                A completion with this name is now recorded. <Link href={`${base}/milestones`}>Open the Milestones tab</Link> to see it.
              </Callout>
            )}

            {submit.status !== 'now_recorded' && (
              <fieldset className="mscomplete__evidence" disabled={locked}>
                <legend className="mscomplete__label">Evidence</legend>
                {noProofs && <p className="mscomplete__plain">No proof is on record for this milestone.</p>}
                {options.proofs.length > 0 && (
                  <RadioGroup
                    legend="Proof on record"
                    hideLegend
                    options={options.proofs.map((p) => ({ value: String(p.id), label: p.label }))}
                    value={m.chosen?.kind === 'proof' ? String(m.chosen.id) : undefined}
                    onChange={(value) => m.setChosen({ kind: 'proof', id: Number(value) })}
                    disabled={locked}
                  />
                )}
                {read.moreFailed && (
                  <p className="mscomplete__plain" role="alert">
                    We couldn&rsquo;t load more proofs. Choose Show more to try again.
                  </p>
                )}
                {options.next_page !== null && (
                  <Button kind="secondary" size="sm" busy={read.loadingMore} busyLabel="Loading…" onClick={() => void m.showMore()}>
                    Show more
                  </Button>
                )}
                {options.can_attach_pdf && (
                  <div className="mscomplete__pdf">
                    <span className="mscomplete__label">Or upload a private PDF</span>
                    <EvidencePicker
                      caseId={caseId}
                      value={m.upload}
                      disabledReason={locked ? 'The completion is being recorded.' : undefined}
                      onChange={(file) => {
                        m.setUpload(file);
                        if (file) m.setChosen({ kind: 'pdf' });
                        else if (usingPdf) m.setChosen(null);
                      }}
                    />
                  </div>
                )}
              </fieldset>
            )}

            {options.can_complete && submit.status !== 'now_recorded' && (
              <>
                <Checkbox label="I confirm this milestone is complete as the SOW describes it." checked={m.confirmed} disabled={locked} onChange={(e) => m.setConfirmed(e.target.checked)} />
                {usingPdf && (
                  <Checkbox label="I have checked this file is the proof for this milestone." checked={m.fileChecked} disabled={locked} onChange={(e) => m.setFileChecked(e.target.checked)} />
                )}
                {!ready && settled && (
                  <p id={NOTE_ID} className="mscomplete__plain mscomplete__why">
                    {missing.join(' ')}
                  </p>
                )}
                <div className={phone ? 'psl-actionbar mscomplete__bar' : 'mscomplete__actions'}>{button}</div>
              </>
            )}
          </div>
        </Panel>
        {options.can_complete && submit.status !== 'now_recorded' && <NextBlock />}
      </div>
    </div>
  );
}

function Route({ caseId, name }: { caseId: string; name: string | null }) {
  const me = useMe();
  const base = `/projects/${encodeURIComponent(caseId)}`;
  usePhoneBack({ label: 'Projects', href: '/projects' });
  if (!hasDestination(me, 'projects')) return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
  if (!usableName(name)) {
    return (
      <section className="psl-panel mscomplete__card" aria-label="Choose a milestone">
        <div className="psl-panel__body">
          <PageTitle>Mark a milestone complete</PageTitle>
          <p className="mscomplete__plain">Choose a milestone from the Milestones tab.</p>
          <p className="mscomplete__plain">
            <Link className={buttonClass('dark', 'lg')} href={`${base}/milestones`}>
              Back to Milestones
            </Link>
          </p>
        </div>
      </section>
    );
  }
  return <Body key={`${caseId}:${name}`} caseId={caseId} name={name} />;
}

/** /projects/<case_id>/milestones/complete?name=<the milestone's name>. */
export function MilestoneCompletePage({ caseId, name }: { caseId: string; name: string | null }) {
  return <Route caseId={routeCaseId(caseId)} name={name} />;
}
