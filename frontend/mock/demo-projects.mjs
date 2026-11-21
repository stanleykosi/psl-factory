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

/** E-PROJECTS item: no PM is chosen yet, so the PM and stage say so instead of a name. */
export const listItem = (p) => ({ case_id: p.case_id, title: p.title, pm: 'Not assigned yet', stage: 'Won · ready to plan', sample: true, reference: p.reference, needs_person: 0, stopped: 0 });

/** E-PROJECT: the journey lists the won RFP run as verified; everything else is empty or unknown. */
export const journey = (p) => ({
  case_id: p.case_id,
  title: p.title,
  lines: [{ line: p.line, state: 'verified', work_id: p.work_id, reference: p.reference, title: p.line, detail: 'RFP won · project created' }],
  next: 'Ready to plan: a PMO Lead chooses the project manager.',
  revision: 1,
  tab_counts: { milestones: 0, documents: 0, registers: 0, actions: 0 },
  facts: [
    { label: 'CONTRACT STAGES', value: '0' },
    { label: 'INVOICES VERIFIED', value: '0' },
    { label: 'WAITING ON PEOPLE', value: '0' },
    { label: 'NEXT MILESTONE', value: 'Unknown', unknown: true },
  ],
});

/** A start-work project option row; value and case id as the fixtures give them. */
export const optionRow = (p) => ({ value: p.case_id, label: p.title, case_id: p.option_case_id, case_revision: 1, sample: true, _personas: DEMO_PROJECT_PERSONAS });
