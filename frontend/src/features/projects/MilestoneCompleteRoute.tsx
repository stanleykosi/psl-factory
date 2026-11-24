'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';

import { LoadingState } from '@/shell/FrameStates';

import { MilestoneCompletePage } from './MilestoneComplete';

function Named({ caseId }: { caseId: string }) {
  return <MilestoneCompletePage caseId={caseId} name={useSearchParams().get('name')} />;
}

/** The name comes from the URL; useSearchParams needs a Suspense boundary so `next build` can prerender the route. */
export function MilestoneCompleteRoute({ caseId }: { caseId: string }) {
  return (
    <Suspense fallback={<LoadingState />}>
      <Named caseId={caseId} />
    </Suspense>
  );
}
