'use client';

// SCR-04 line drawer shell: the frame, back and close, the project picker, the line's own fields (lines/) and one start
// button. The start state machine is useStart; the line supplies its fields, required checks, body and server-name map.
// Errors come only from the server: a 422 names fields inline and draws a name this line does not know as its own box;
// a 409, 403 or 404 keeps what was typed; an uncertain result locks the form until "Check again".
import { Button, Callout, Icon, ValidationSummary } from '@/components';
import { SignedOutState } from '@/shell/FrameStates';

import { DrawerFrame, useWide } from './DrawerFrame';
import { CHANGED_SINCE_OPENED } from './labels';
import type { LineForm } from './lines';
import { ProjectPicker } from './ProjectPicker';
import type { FieldProblem } from './types';
import { NOT_CONFIRMED, useStart } from './useStart';

type Props = {
  form: LineForm;
  lineKey: string;
  /** Back and "change line" go to the chooser. */
  onBack: () => void;
  onClose: () => void;
  onStarted: (workId: string) => void;
  pathname: string;
  /** A start answered 409: the caller may read its record again. */
  onConflict?: () => void;
};

/** A 422 problem for a name this line does not know, named from its key. */
function ProblemBox({ problem }: { problem: FieldProblem }) {
  const name = problem.name.replace(/[._]/g, ' ');
  return (
    <div className="psl-field sw-field" data-field={problem.name}>
      <span className="psl-label">{name.charAt(0).toUpperCase() + name.slice(1)}</span>
      <span className="psl-input is-error sw-display">—</span>
      <span className="psl-error">
        <Icon name="warn" />
        <span>{problem.message}</span>
      </span>
    </div>
  );
}

export function LineDrawer({ form, lineKey, onBack, onClose, onStarted, pathname, onConflict }: Props) {
  const wide = useWide();
  const start = useStart(form, onStarted, onConflict);
  const { notice } = start;
  const readOnly = start.busy || start.uncertain;
  const changeLine = (
    <Button kind="text" size="sm" className="sw-change" onClick={onBack}>
      change line
    </Button>
  );
  const subline = wide ? <>Line chosen from the Start work menu · {changeLine}</> : <>Step 2 of 2 · {changeLine}</>;
  const cancel = (
    <Button kind="secondary" className="sw-secondary" onClick={onClose}>
      Cancel
    </Button>
  );

  if (start.signedOut) {
    return (
      <DrawerFrame eyebrow="START WORK" title={form.drawerTitle} subline={subline} onClose={onClose} footer={cancel} focusKey="signed-out">
        <SignedOutState pathname={pathname} />
      </DrawerFrame>
    );
  }

  const footer = (
    <>
      {start.uncertain && <span className="psl-hint sw-foothint">If it started, it will appear in My work.</span>}
      {wide && cancel}
      <Button kind="start" className="sw-primary" busy={start.busy} busyLabel="Starting…" onClick={() => void start.submit()}>
        {start.uncertain ? 'Check again' : form.startLabel}
      </Button>
    </>
  );

  return (
    <DrawerFrame eyebrow="START WORK" title={form.drawerTitle} subline={subline} onClose={onClose} footer={footer} focusKey={`line-${lineKey}`}>
      <ValidationSummary problems={start.problems} attempt={start.attempt} />
      {notice?.kind === 'invalid' && notice.general.length > 0 && (
        <Callout kind="problem">
          <span className="sw-stack">
            {notice.general.map((message) => (
              <span key={message}>{message}</span>
            ))}
          </span>
        </Callout>
      )}
      {notice?.kind === 'stale' && (
        <div role="alert">
          <Callout kind="warning">
            {CHANGED_SINCE_OPENED}
            {notice.message && <> {notice.message}</>}
          </Callout>
        </div>
      )}
      {notice?.kind === 'problem' && <Callout kind="problem">{notice.message}</Callout>}
      {notice?.kind === 'uncertain' && (
        <div role="alert">
          <Callout kind="warning">{NOT_CONFIRMED}</Callout>
        </div>
      )}
      <ProjectPicker lineKey={lineKey} value={start.project} onChange={start.chooseProject} disabled={readOnly} error={start.errors.project} />
      <form.Form values={start.values} setValue={start.setValue} errors={start.errors} readOnly={readOnly} caseId={start.project?.case_id ?? null} />
      {notice?.kind === 'invalid' && notice.unmatched.map((problem, at) => <ProblemBox key={`${problem.name}-${at}`} problem={problem} />)}
    </DrawerFrame>
  );
}
