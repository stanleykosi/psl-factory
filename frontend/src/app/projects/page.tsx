import type { Metadata } from 'next';

import { ProjectsPage } from '@/features/projects/ProjectsPage';

export const metadata: Metadata = { title: 'Projects · PSL Factory' };

export default function Page() {
  return <ProjectsPage />;
}
