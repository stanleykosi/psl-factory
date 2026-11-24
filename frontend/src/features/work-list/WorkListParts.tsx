'use client';

// The parts every screen on the live work list draws the same way: the line filter, the error states and the footer
// (Show more, Keep looking, Try again, and the coverage notes). No page-size control: the server's 8 is not a setting.
import { useState } from 'react';

import type { ApiError } from '@/api/errors';
import { Button, EmptyState, FilterPanel, Loading, RadioGroup, Skeleton } from '@/components';
import { SignedOutState } from '@/shell/FrameStates';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';

import { coverageNotes } from './coverage';
import { asLineKey } from './labels';
import type { LineKey, MoreState, WorkCoverage, WorkLine } from './types';

import './work-list.css';

const ALL_LINES = '';

/** CMP-22 filter panel with one choice, the line; it edits a draft and only "Show results" applies it. */
export function LineFilter({ lines, applied, onApply, onClose }: { lines: WorkLine[]; applied?: LineKey; onApply: (line: LineKey | undefined) => void; onClose: () => void }) {
  const [draft, setDraft] = useState<LineKey | undefined>(applied);
  return (
    <FilterPanel applyLabel="Show results" onApply={() => onApply(draft)} onClear={() => setDraft(undefined)} onClose={onClose}>
      <RadioGroup
        legend="Line"
        name="work-line"
        value={draft ?? ALL_LINES}
        onChange={(value) => setDraft(value === ALL_LINES ? undefined : asLineKey(value))}
        options={[{ value: ALL_LINES, label: 'All lines' }, ...lines.map((line) => ({ value: line.key, label: line.title }))]}
      />
    </FilterPanel>
  );
}

/** The frame's loading look, with this list's own words ("Loading verified outputs…"). */
export function WorkListLoading({ children }: { children: string }) {
  return (
    <div className="shell-loading">
      <Skeleton widths={[90, 70, 80]} />
      <Loading>{children}</Loading>
    </div>
  );
}

/** 401 signs out, 403 is a closed list (no retry), anything else is the error card with Try again. */
export function WorkListError({ error, pathname, what, onRetry }: { error: ApiError; pathname: string; what: string; onRetry: () => void }) {
  if (error.kind === 'unauthenticated') return <SignedOutState pathname={pathname} />;
  if (error.kind === 'forbidden') return <EmptyState level={2} title="This list isn’t open to your role." className="wl-empty">Nothing is shown here for your account.</EmptyState>;
  return <WorkErrorCard message={`We couldn’t load ${what}. Your work is safe; nothing was changed.`} error={error} onRetry={onRetry} />;
}

const MORE_LABEL: Record<Exclude<MoreState, 'done'>, string> = { idle: 'Show more', loading: 'Show more', failed: 'Try again', 'keep-looking': 'Keep looking' };

/** Under the list: the more button (none once the list is complete) and the quiet coverage lines. */
export function WorkListFooter({ more, onMore, coverage, asOf }: { more: MoreState; onMore: () => void; coverage: WorkCoverage; asOf: string }) {
  return (
    <div className="wl-footer">
      {more !== 'done' && (
        <div className="wl-more">
          {more === 'failed' && (
            <p className="wl-note" role="alert">
              We couldn’t load more. The rows above are unchanged.
            </p>
          )}
          <Button kind="secondary" busy={more === 'loading'} busyLabel="Loading…" onClick={onMore}>
            {MORE_LABEL[more]}
          </Button>
        </div>
      )}
      {coverageNotes(coverage, asOf).map((note) => (
        <p key={note} className="wl-note">
          {note}
        </p>
      ))}
    </div>
  );
}
