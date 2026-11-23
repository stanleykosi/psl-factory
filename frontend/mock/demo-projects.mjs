// Projects the live demo creates (D-164): when a demo RFP line run is verified (the RFP is won), one project for its client
// appears: in every project picker, in the Projects list and as a basic project page. The store is module-level, as the logged
// RFPs of start-work.mjs are; reset() clears it. Sample data only: no PM is chosen and no business rule is decided here.
export const DEMO_PROJECT_PERSONAS = ['finance_lead', 'pm', 'ceo', 'pmo_lead']; // as the rows of fixtures/projects/list.json
const projects = [];

const pad = (n) => String(n).padStart(4, '0');

export function addDemoProject({ client, run }) {
  const n = projects.length + 1;
  const project = {
    case_id: `P-9${pad(n).slice(1)}`,
    option_case_id: `C-9${pad(n).slice(1)}`,
    title: `${client} · new engagement`,
    work_id: run.id,
    reference: run.reference,
    line: run.line,
  };
  projects.push(project);
  return project;
}

export const demoProjects = () => projects;
export const demoProject = (caseId) => projects.find((p) => p.case_id === caseId);
export const resetDemoProjects = () => { projects.length = 0; };

/** True when the persona may see demo projects (as the sample list). */
export const demoVisible = (persona) => DEMO_PROJECT_PERSONAS.includes(persona);

// The live-shape ids: the project's fixed UUID (P-9001 is 00000000-0000-4000-8000-000000009001), and the work id as an integer.
export const uuidOf = (caseId) => `00000000-0000-4000-8000-${caseId.slice(2).padStart(12, '0')}`;

/** GET /projects item: no manager is chosen yet, so there is none; the phase says the project was won. */
export const listItem = (p) => ({ case_id: uuidOf(p.case_id), title: p.title, revision: 1, sample: true, manager: null, lifecycle: 'active', phase: 'Won · ready to plan', reviews: 0, exceptions: 0, django_url: `/projects/${uuidOf(p.case_id)}/` });

/** GET /projects/{case_id}: the journey lists the won RFP run as verified; everything else is empty or not available. */
export const journey = (p) => {
  const caseId = uuidOf(p.case_id);
  const workId = Number(p.work_id.slice(2));
  const now = new Date().toISOString();
  return {
    case_id: caseId,
    title: p.title,
    revision: 1,
    sample: true,
    tabs: [
      { key: 'journey', title: 'Journey', django_url: `/projects/${caseId}/`, api_url: `/api/v1/projects/${caseId}` },
      { key: 'milestones', title: 'Milestones', django_url: `/projects/${caseId}/milestones/`, api_url: `/api/v1/projects/${caseId}/milestones` },
      { key: 'documents', title: 'Documents', django_url: `/projects/${caseId}/documents/`, api_url: `/api/v1/projects/${caseId}/documents` },
      { key: 'money', title: 'Money', django_url: `/projects/${caseId}/money/`, api_url: `/api/v1/projects/${caseId}/money` },
      { key: 'registers', title: 'Registers', django_url: `/projects/${caseId}/registers/`, api_url: `/api/v1/projects/${caseId}/registers` },
      { key: 'actions', title: 'Actions', django_url: `/projects/${caseId}/actions/`, api_url: `/api/v1/projects/${caseId}/actions` },
    ],
    items: [{ id: workId, line: p.line, reference: p.reference ?? null, state: 'Verified', started: now, updated: now, django_url: `/work/${workId}/`, api_url: `/api/v1/work/${workId}` }],
    page: 1,
    next_page: null,
    as_of: now,
    facts: { total: 1, waiting: 0, stopped: 0, finance: null, engagement: null },
    assistant: [],
  };
};

/** A start-work project option row; value and case id as the fixtures give them. */
export const optionRow = (p) => ({ value: p.case_id, label: p.title, case_id: p.option_case_id, case_revision: 1, sample: true, _personas: DEMO_PROJECT_PERSONAS });
