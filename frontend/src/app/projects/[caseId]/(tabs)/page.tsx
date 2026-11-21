import type { Metadata } from 'next';

import { ProjectTabBody } from '@/features/projects/ProjectJourney';

// The title never names the project: a person without access must not learn it from the tab.
export const metadata: Metadata = { title: 'Project · PSL Factory' };

export default function ProjectPage() {
  return <ProjectTabBody />;
}
