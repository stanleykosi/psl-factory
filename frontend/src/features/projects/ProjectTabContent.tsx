'use client';

// The content of the Milestones, Documents, Registers and Actions tabs inside the project page's tab panel. The page (header, tab
// bar, access to the project) is ProjectJourney's; these tabs only read E-PROJECT-TAB and draw its rows, read-only.
import { Suspense } from 'react';

import { ActionsTab } from './ActionsTab';
import { DocumentsTab } from './DocumentsTab';
import { MilestonesTab } from './MilestonesTab';
import type { Journey } from './model';
import { RegistersTab } from './RegistersTab';
import type { ListTab } from './tabsModel';

import './project-tabs.css';

/** "PM Tunde Bello · Route A": each part only when present; hidden on phones, as the Journey line is. */
function PmRoute({ journey }: { journey: Journey }) {
  const engagement = journey.facts.engagement;
  const text = [engagement?.manager && `PM ${engagement.manager}`, engagement?.route].filter(Boolean).join(' · ');
  return text ? <p className="ptabs__route">{text}</p> : null;
}

export function ProjectTabContent({ caseId, journey, base, tab }: { caseId: string; journey: Journey; base: string; tab: ListTab }) {
  // useSearchParams needs a Suspense boundary so `next build` can prerender the route.
  return (
    <Suspense fallback={null}>
      {tab !== 'registers' && <PmRoute journey={journey} />}
      {tab === 'milestones' && <MilestonesTab caseId={caseId} pathname={`${base}/milestones`} />}
      {tab === 'documents' && <DocumentsTab caseId={caseId} />}
      {tab === 'registers' && <RegistersTab caseId={caseId} base={base} />}
      {tab === 'actions' && <ActionsTab caseId={caseId} base={base} />}
    </Suspense>
  );
}
