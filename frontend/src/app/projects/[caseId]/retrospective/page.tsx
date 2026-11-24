import type { Metadata } from 'next';
import { Suspense } from 'react';

import { routeCaseId } from '@/features/projects/model';
import { RetrospectivePage } from '@/features/retrospective/RetrospectiveView';
import { LoadingState } from '@/shell/FrameStates';

// The title never names the project: a person without access must not learn it from the tab.
export const metadata: Metadata = { title: 'Project retrospective · PSL Factory' };

/** /projects/<case_id>/retrospective?dossier=&meeting=&version=: a page of its own, not a project tab. */
export default async function RetrospectiveRoute({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = await params;
  return (
    <Suspense fallback={<LoadingState />}>
      <RetrospectivePage caseId={routeCaseId(caseId)} />
    </Suspense>
  );
}
