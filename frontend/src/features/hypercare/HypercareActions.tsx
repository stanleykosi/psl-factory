'use client';

// F-115: what the stability panel draws after its own sections: the open issues (their own read, with their own Try again) and the next
// step. It sends nothing. Pause and continue are the work item's own controls (F-87), listed by the item's `actions`.
import { Button, Callout } from '@/components';
import type { LineActionsProps } from '@/features/workspace/adapter';
import { SectionView } from '@/features/workspace/Sections';

import { criteriaOf, issuesSection, nextSection, type Stability } from './hypercareModel';
import { useHypercareIssues } from './useHypercareIssues';

export function HypercareActions({ readback, ctx }: LineActionsProps<Stability>) {
  const { state, retry } = useHypercareIssues(ctx.caseId, readback.assessment_id);
  const next = nextSection(readback);
  return (
    <>
      {state.status === 'ready' && <SectionView section={issuesSection(state.open, criteriaOf(readback))} level={2} />}
      {state.status === 'failed' && (
        <Callout kind="warning">
          Open issues couldn’t be loaded.{' '}
          <Button kind="secondary" size="sm" onClick={retry}>
            Try again
          </Button>
        </Callout>
      )}
      {next && <SectionView section={next} level={2} />}
    </>
  );
}
