// Line runs of the live demo (D-155, demo.mjs). Starting a line in the demo creates a work item that runs through that line's
// stations on the mock's clock. There is no timer: every read advances the runs by the time that has passed (`now`), so a run
// is the same whether one page or none is watching it.
//
// Stations: the names of the line's own fixture item (start-work.mjs WORK_IDS); a line without one gets a generic sequence
// (Intake, Agent drafts, Review, Decision, Verified). One station per line is the human one (HUMAN below); the rest are the
// agent's. An agent station ticks its three steps, `stepMs` apart (each step goes working -> done), then the item moves on.
// At the human station the item waits: it is Needs me for the persona who decides (DECIDERS; the CEO when the starter is that
// persona and the step approves the starter's own work, so no one approves what they started; an assignment such as
// "Assign PM" stays with its own role, `own: true`) and Waiting for the starter, and an alert is raised. Approve moves it on, Return sends it back to the agent
// station before it for rework (a new draft, a new task), Reject stops it. The last station ends verified, in Done, with a
// history entry for every step. Sample data only: nothing is sent to anyone and no rule is decided here.
import { WORK_IDS } from './start-work.mjs';

export const LINE_STEP_MS = 2500;

const AGENTS = {
  chidi: { name: 'Chidi', role: 'Finance agent' },
  tola: { name: 'Tola', role: 'PMO agent' },
  zainab: { name: 'Zainab', role: 'HR agent' },
};
const ROLES = { finance_lead: 'Finance Lead', pmo_lead: 'PMO Lead', hr_lead: 'HR Lead', ceo: 'CEO' };
const FACTS = ['drafted', 'reviewed', 'approved', 'sent', 'receipt_recorded', 'verified'];
const FINANCE = { agent: 'chidi', decider: 'finance_lead' };
const PMO = { agent: 'tola', decider: 'pmo_lead' };
// Per line key: the agent, who decides, and which of the line's stations is the human one.
const LINES = {
  invoice: { ...FINANCE, human: 'Finance review' },
  income_schedules: { ...FINANCE, human: 'Finance review' },
  ledger_sources: { ...FINANCE, human: 'Independent review' },
  fixed_assets: { ...FINANCE, human: 'Register review' },
  cash_forecast: { ...FINANCE, human: 'Review' },
  weekly_report: { ...PMO, human: 'PM review' },
  minutes: { ...PMO, human: 'PM review' },
  issue_followup: { ...PMO, human: 'Find the owner', own: true },
  change_request: { ...PMO, human: 'Decide' },
  emergency_change: { ...PMO, human: 'Preauthorise' },
  escalation: { ...PMO, human: 'Review' },
  leadership_report: { ...PMO, human: 'Review' },
  rfp_intake: { ...PMO, human: 'Assign PM', own: true },
  hr_staff_list: { agent: 'zainab', decider: 'hr_lead', human: 'Confirm the list' },
};
const GENERIC = { ...PMO, human: 'Decision', stations: ['Intake', 'Agent drafts', 'Review', 'Decision', 'Verified'] };
const KINDS = { decision: 'decision', agent: 'agent_work' };
const STATE = { running: 'processing', waiting: 'waiting', done: 'verified', cancelled: 'cancelled' };

const pad = (n, width) => String(n).padStart(width, '0');
const iso = (ms) => new Date(ms).toISOString();

export function createLineRuns({ now = () => Date.now(), stepMs = LINE_STEP_MS, work, me, raise = () => {} }) {
  const runs = new Map();
  const byKey = new Map();
  let counter = 0;
  let alerts = 0;

  const person = (persona) => `${me[persona].name} · ${ROLES[persona] ?? me[persona].roles[0]}`;
  const agentOf = (run) => AGENTS[run.agent];
  const roleOf = (run) => ROLES[run.decider];
  const station = (run, i = run.idx) => run.stations[Math.min(i, run.stations.length - 1)];

  function note(run, at, actor_kind, actor, event, extra = {}) {
    run.history.push({ at, actor_kind, actor, event, restricted: false, ...extra });
  }
  const agentNote = (run, at, event, detail) => note(run, at, 'agent', `${agentOf(run).name} · ${agentOf(run).role}`, event, { _kind: KINDS.agent, ...(detail ? { detail } : {}) });
  const alert = (persona, run, text) => {
    alerts += 1;
    raise(persona, { id: `N-D${pad(alerts, 3)}`, work_id: run.id, agent: run.agent, text, at: iso(now()), read: false, reference: run.reference, delivered_via: ['in_app'] });
  };

  /** The three steps of an agent station; a station sent back for rework starts by reading the note. */
  function stepsOf(run, i) {
    const name = station(run, i);
    return [
      run.reworked.has(i) ? `Read the note that came back on “${name}”` : `Read what “${name}” needs`,
      `Worked on “${name}”`,
      `Checked the result of “${name}”`,
    ];
  }

  function advance(run) {
    const at = now();
    while (run.state === 'running') {
      if (run.idx === run.humanAt) {
        run.state = 'waiting';
        run.revision += 1;
        run.taskRevision = run.revision;
        run.taskId = `T-${run.id.slice(2)}-${run.rework + 1}`;
        run.tasks.set(run.taskId, run.taskRevision);
        run.seen = true;
        note(run, iso(run.stationStartedAt), 'factory', 'Factory', `Waiting for the ${roleOf(run)} to decide “${station(run)}”`);
        alert(run.decider, run, `${run.title} needs your decision`);
        break;
      }
      const steps = stepsOf(run, run.idx);
      while (run.logged < steps.length && run.stationStartedAt + (run.logged + 1) * stepMs <= at) {
        agentNote(run, iso(run.stationStartedAt + (run.logged + 1) * stepMs), steps[run.logged]);
        run.logged += 1;
      }
      const end = run.stationStartedAt + steps.length * stepMs;
      if (at < end) break;
      run.lastSteps = steps;
      run.idx += 1;
      run.stationStartedAt = end;
      run.logged = 0;
      run.revision += 1;
      if (run.idx >= run.stations.length) {
        run.state = 'done';
        note(run, iso(end), 'factory', 'Factory', 'Verified', { detail: 'Every station is done.' });
        alert(run.starter, run, `${run.title} is verified`);
      }
    }
  }

  const tick = () => runs.forEach(advance);

  function start({ key, lineKey, persona }) {
    if (byKey.has(key)) return byKey.get(key);
    const def = LINES[lineKey] ?? GENERIC;
    const fixture = work[WORK_IDS[lineKey]];
    const stations = def.stations ?? fixture?.stations?.map((s) => s.name) ?? GENERIC.stations;
    const humanAt = Math.max(1, stations.indexOf(def.human));
    counter += 1;
    const at = now();
    const run = {
      id: `W-9${pad(counter, 3)}`,
      lineKey,
      line: fixture?.line ?? lineKey,
      reference: `DEMO-${pad(counter, 4)}`,
      agent: def.agent,
      decider: def.decider === persona && !def.own ? 'ceo' : def.decider,
      starter: persona,
      stations,
      humanAt,
      startedAt: at,
      stationStartedAt: at,
      idx: 0,
      logged: 0,
      revision: 1,
      state: 'running',
      rework: 0,
      reworked: new Set(),
      lastSteps: [],
      history: [],
      tasks: new Map(),
      seen: false,
    };
    run.title = `${run.line} · Demo ${counter}`;
    note(run, iso(at), 'factory', 'Factory', 'Started the line', { detail: `Started by ${me[persona].name}` });
    runs.set(run.id, run);
    byKey.set(key, run);
    advance(run);
    return run;
  }

  function task(run, persona) {
    const mine = persona === run.decider;
    return {
      id: run.taskId,
      kind: 'decide',
      title: `Decide “${station(run)}”`,
      required_role: roleOf(run),
      you_can_act: mine,
      revision: run.taskRevision,
      ...(mine ? {} : { cannot_act_reason: 'not_your_role' }),
      decision: {
        version: { label: `Draft v${run.rework + 1}`, number: run.rework + 1 },
        basis: 'Sample draft from the live demo. No agent ran.',
        prepared_by: { name: agentOf(run).name, role: agentOf(run).role, is_you: false, with_agent: run.agent },
        chain: {
          steps: [{ position: 1, role: roleOf(run), person: me[run.decider].name, status: 'current', is_you: mine }],
          ...(mine ? { your_step: 1 } : {}),
          step_count: 1,
        },
      },
    };
  }

  function item(run, persona) {
    const at = now();
    const n = run.stations.length;
    const label = (i) => {
      if (run.state === 'done') return i === n - 1 ? 'verified' : 'done';
      if (i !== run.idx) return i < run.idx ? 'done' : 'not_started';
      return run.state === 'cancelled' ? 'stopped' : run.state === 'waiting' ? 'current_person' : 'current_agent';
    };
    const held = (i) => {
      if (i !== run.idx || run.state === 'done' || run.state === 'cancelled') return {};
      return { held_by: run.state === 'waiting' ? { kind: 'role', name: roleOf(run), is_you: persona === run.decider } : { kind: 'agent', name: agentOf(run).name, is_you: false } };
    };
    const earned = run.state === 'done' ? FACTS.length : Math.floor((run.idx / n) * FACTS.length);
    const ticking = run.state === 'running' ? Math.min(stepsOf(run, run.idx).length - 1, Math.floor((at - run.stationStartedAt) / stepMs)) : -1;
    const steps = run.state === 'running'
      ? stepsOf(run, run.idx).slice(0, ticking + 1).map((text, i) => ({ text, status: i < ticking ? 'done' : 'working' }))
      : run.lastSteps.map((text) => ({ text, status: 'done' }));
    const next = {
      running: `${agentOf(run).name} is working on “${station(run)}”.`,
      waiting: `A ${roleOf(run)} decides “${station(run)}”.`,
      done: 'Done. Every step is in the history.',
      cancelled: `Stopped: “${station(run)}” was rejected.`,
    }[run.state];
    return {
      id: run.id,
      title: run.title,
      line: run.line,
      reference: run.reference,
      state: STATE[run.state],
      revision: run.revision,
      stations: run.stations.map((name, i) => ({ name, status: label(i), ...held(i) })),
      facts: FACTS.map((name, i) => ({ name, status: i < earned ? 'earned' : i === earned && run.state !== 'done' && run.state !== 'cancelled' ? 'current' : 'not_yet' })),
      tasks: run.state === 'waiting' ? [task(run, persona)] : [],
      agent: { name: agentOf(run).name, status: { running: 'working', waiting: 'waiting', done: 'done', cancelled: 'stopped' }[run.state], steps, started_at: iso(run.stationStartedAt) },
      next_step: next,
      started_by: { name: me[run.starter].name, role: ROLES[run.starter] ?? me[run.starter].roles[0], is_you: persona === run.starter },
      started_at: iso(run.startedAt),
      sample: true,
    };
  }

  function row(run, persona, at) {
    const isStarter = persona === run.starter;
    const isDecider = persona === run.decider;
    if (!isStarter && !(isDecider && run.seen)) return undefined;
    const n = run.stations.length;
    const finished = run.state === 'done' || run.state === 'cancelled';
    const waitingOnMe = run.state === 'waiting' && isDecider;
    const waiting = finished ? undefined : waitingOnMe ? 'me' : run.state === 'waiting' ? 'someone_else' : 'agent';
    return {
      personas: [persona],
      queue: finished ? 'done' : waitingOnMe ? 'needs_me' : 'waiting_on_others',
      ...(waiting ? { waiting } : {}),
      item: {
        id: run.id,
        title: run.title,
        line: run.line,
        line_key: run.lineKey,
        reference: run.reference,
        kind: waitingOnMe ? 'decide' : 'started',
        state: STATE[run.state],
        station: { index: Math.min(run.idx + 1, n), count: n, name: station(run) },
        waiting_on: finished ? 'Nobody' : run.state === 'waiting' ? roleOf(run) : 'Agent',
        age_seconds: Math.max(0, Math.floor((at - run.startedAt) / 1000)),
        sample: true,
        agent: run.agent,
      },
    };
  }

  /** The decision on the task now open: Approve moves on, Return goes back for rework, Reject stops. */
  function decide(taskId, verdict, text, persona) {
    const run = [...runs.values()].find((r) => r.taskId === taskId);
    const at = now();
    const where = station(run);
    const detail = typeof text === 'string' && text.trim() !== '' ? `Note: “${text.trim()}”` : undefined;
    const version = `v${run.rework + 1}`;
    const verbs = { approve: 'Approved', return: 'Returned', reject: 'Rejected' };
    note(run, iso(at), 'person', person(persona), `${verbs[verdict]} “${where}”`, { _kind: KINDS.decision, version, ...(detail ? { detail } : {}) });
    run.tasks.set(taskId, run.taskRevision + 1);
    run.revision += 1;
    if (verdict === 'reject') {
      run.state = 'cancelled';
      alert(run.starter, run, `${run.title} was rejected`);
    } else if (verdict === 'return') {
      run.rework += 1;
      run.idx = run.humanAt - 1;
      run.reworked.add(run.idx);
      run.stationStartedAt = at;
      run.logged = 0;
      run.state = 'running';
    } else {
      run.idx += 1;
      run.stationStartedAt = at;
      run.logged = 0;
      run.state = 'running';
    }
    advance(run);
    return STATE[run.state];
  }

  return {
    start,
    tick,
    decide,
    owns: (workId) => runs.has(workId),
    item(workId, persona) {
      const run = runs.get(workId);
      if (!run) return undefined;
      advance(run);
      return item(run, persona);
    },
    history(workId) {
      const run = runs.get(workId);
      if (!run) return undefined;
      advance(run);
      return { items: run.history.map((entry) => ({ ...entry })).reverse(), as_of: iso(now()) };
    },
    rows(persona) {
      tick();
      const at = now();
      return [...runs.values()].map((run) => row(run, persona, at)).filter(Boolean).sort((a, b) => a.item.age_seconds - b.item.age_seconds);
    },
    /** A task of a run: the open one with its item, or a decided one (revision moved on, you_can_act false) for the stale 409. */
    findTask(taskId, persona) {
      const run = [...runs.values()].find((r) => r.tasks.has(taskId));
      if (!run) return undefined;
      advance(run);
      const built = item(run, persona);
      const open = built.tasks.find((t) => t.id === taskId);
      return { workId: run.id, item: built, task: open ?? { id: taskId, kind: 'decide', title: 'Decided', required_role: roleOf(run), you_can_act: false, revision: run.tasks.get(taskId) } };
    },
    reset() {
      runs.clear();
      byKey.clear();
      counter = 0;
      alerts = 0;
    },
  };
}
