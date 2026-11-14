import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { PROJECT_TABS, routeCaseId, type ProjectTab } from '@/features/projects/model';
import { ProjectJourneyPage } from '@/features/projects/ProjectJourney';


export const metadata: Metadata = { title: 'Project · PSL Factory' };

/** /projects/<case_id>/<tab>: the project's other tabs; their contents come with FE-M3-PROJECT-TABS. */
export default async function ProjectTabPage({ params }: { params: Promise<{ caseId: string; tab: string }> }) {
  const { caseId, tab } = await params;
  const known = PROJECT_TABS.find((t) => t.key !== 'journey' && t.key === tab);
  if (!known) notFound();
  return <ProjectJourneyPage caseId={routeCaseId(caseId)} tab={known.key as ProjectTab} />;
}
