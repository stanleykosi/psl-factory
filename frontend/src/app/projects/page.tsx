import type { Metadata } from 'next';

import { DestinationPage } from '@/shell/DestinationPage';

export const metadata: Metadata = { title: 'Projects · PSL Factory' };

export default function ProjectsPage() {
  return <DestinationPage destination="projects" />;
}
