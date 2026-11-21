import type { ReactNode } from 'react';

import { routeCaseId } from '@/features/projects/model';
import { ProjectLayoutFrame } from '@/features/projects/ProjectJourney';

/** One frame and one project read for every tab; the tab pages draw only the panel. */
export default async function ProjectLayout({ children, params }: { children: ReactNode; params: Promise<{ caseId: string }> }) {
  const { caseId } = await params;
  return <ProjectLayoutFrame caseId={routeCaseId(caseId)}>{children}</ProjectLayoutFrame>;
}
