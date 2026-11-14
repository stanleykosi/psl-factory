import type { Metadata } from 'next';

import { routeCaseId } from '@/features/projects/model';
import { ProjectJourneyPage } from '@/features/projects/ProjectJourney';

// The title never names the project: a person without access must not learn it from the tab.
export const metadata: Metadata = { title: 'Project · PSL Factory' };

export default async function ProjectPage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = await params;
  return <ProjectJourneyPage caseId={routeCaseId(caseId)} />;
}
