import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { PROJECT_TABS } from '@/features/projects/model';
import { ProjectTabBody } from '@/features/projects/ProjectJourney';

export const metadata: Metadata = { title: 'Project · PSL Factory' };

/** /projects/<case_id>/<tab>: the project's other tabs; the frame around them comes from the layout. */
export default async function ProjectTabPage({ params }: { params: Promise<{ tab: string }> }) {
  const { tab } = await params;
  if (!PROJECT_TABS.some((t) => t.key !== 'journey' && t.key === tab)) notFound();
  return <ProjectTabBody />;
}
