# PSL operations factory — frontend and data API — delivery

Dates, assignees and estimates are unassigned unless supported in the canonical model.

## M-1 — First feature, frontend: My work and one decision against the API contract

```json
{
  "id": "M-1",
  "title": "First feature, frontend: My work and one decision against the API contract",
  "refs": [
    "T-FRONTEND-SHELL",
    "FE-MYWORK",
    "FE-WORKITEM",
    "FE-DECIDE",
    "D-FIRST-FEATURE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-DECISIONS-V2"
  ],
  "owner_role": "delivery owner",
  "exit_criteria": [
    "Screens match the approved canvas on desktop and phone",
    "A-ACCESSIBILITY passes",
    "Runs on the mock server built from openapi.json with sample data"
  ],
  "gate_ids": [
    "D-FIRST-FEATURE",
    "D-PAGING",
    "D-UPDATES"
  ]
}
```

Unresolved gates: none

## M-1B — First feature, backend: the API for My work and decisions

```json
{
  "id": "M-1B",
  "title": "First feature, backend: the API for My work and decisions",
  "refs": [
    "T-FOUNDATION",
    "T-MYWORK",
    "T-WORKITEM",
    "T-DECIDE"
  ],
  "evidence": [
    "S-BACKEND"
  ],
  "owner_role": "delivery owner",
  "exit_criteria": [
    "A-ME, A-MYWORK, A-WORKITEM, A-HISTORY, A-DECIDE, A-STALE, A-NOT-YOURS pass on PostgreSQL"
  ],
  "gate_ids": [
    "D-API-STYLE",
    "D-AUTH"
  ]
}
```

Unresolved gates: D-API-STYLE, D-AUTH, D-TASK-DECISION-VIEW, D-WORKITEM-DETAIL, D-WORKLIST-FILTERS

## M-1C — First feature connected end to end

```json
{
  "id": "M-1C",
  "title": "First feature connected end to end",
  "refs": [
    "FE-CONNECT-1"
  ],
  "evidence": [
    "S-SCREENS"
  ],
  "owner_role": "delivery owner",
  "exit_criteria": [
    "The frontend runs on the real API with sample data; the same scenarios pass"
  ],
  "gate_ids": []
}
```

Unresolved gates: D-API-STYLE, D-AUTH, D-TASK-DECISION-VIEW, D-WORKITEM-DETAIL, D-WORKLIST-FILTERS

## M-2 — Start, respond and recover

```json
{
  "id": "M-2",
  "title": "Start, respond and recover",
  "refs": [
    "T-START",
    "T-RESPONSE",
    "T-EXCEPTIONS",
    "T-BACKEND-ROLES",
    "FE-M2",
    "FE-M2A",
    "FE-M2B",
    "FE-DECIDE-VARIANTS"
  ],
  "evidence": [
    "S-SCREENS"
  ],
  "owner_role": "delivery owner",
  "exit_criteria": [
    "A-START, A-RESPONSE, A-RECONCILE, A-RESUME pass",
    "A-DECIDE-VARIANTS passes once D-DECISION-VARIANTS is decided"
  ],
  "gate_ids": [
    "D-RETURN",
    "D-DECISION-VARIANTS"
  ]
}
```

Unresolved gates: D-API-STYLE, D-AUTH, D-DECISION-VARIANTS, D-RETURN, D-TASK-DECISION-VIEW, D-WORKITEM-DETAIL

## M-3 — Projects, overview, Finance, payroll and setup

```json
{
  "id": "M-3",
  "title": "Projects, overview, Finance, payroll and setup",
  "refs": [
    "T-PROJECTS",
    "T-FLOOR",
    "T-FINANCE",
    "T-PAYROLL",
    "T-SETUP",
    "FE-M3",
    "FE-M3-PROJECTS",
    "FE-M3-OVERVIEW",
    "FE-M3-FINANCE",
    "FE-M3-SETUP"
  ],
  "evidence": [
    "S-SCREENS"
  ],
  "owner_role": "delivery owner",
  "exit_criteria": [
    "A-PROJECT, A-REPORT, A-OVERVIEW, A-MONTHEND, A-PAYROLL, A-SETUP pass"
  ],
  "gate_ids": []
}
```

Unresolved gates: D-API-STYLE, D-AUTH

## M-4 — Alerts and assistant

```json
{
  "id": "M-4",
  "title": "Alerts and assistant",
  "refs": [
    "T-ALERTS",
    "T-ASSISTANT",
    "FE-M4"
  ],
  "evidence": [
    "S-SCREENS"
  ],
  "owner_role": "delivery owner",
  "exit_criteria": [
    "A-ALERTS and A-ASSISTANT pass on mock and synthetic providers"
  ],
  "gate_ids": [
    "D-ALERT-PROVIDERS",
    "D-AGENT-PROVIDER",
    "D-NOTIFY-MODEL",
    "D-CONVERSATION-MODEL"
  ]
}
```

Unresolved gates: D-AGENT-PROVIDER, D-ALERT-PROVIDERS, D-API-STYLE, D-AUTH, D-CONVERSATION-MODEL, D-NOTIFY-MODEL, D-TASK-DECISION-VIEW, D-WORKITEM-DETAIL

## T-FOUNDATION — API: apps/api, session and CSRF, error shape, /me

```json
{
  "id": "T-FOUNDATION",
  "title": "API: apps/api, session and CSRF, error shape, /me",
  "refs": [
    "E-ME",
    "R-SESSION"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [],
  "gate_ids": [],
  "acceptance": [
    "A-ME"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-AUTH

## T-FRONTEND-SHELL — Frontend: Next.js app, design system tokens and components, top bar, phone bar, API client with mock server from openapi.json

```json
{
  "id": "T-FRONTEND-SHELL",
  "title": "Frontend: Next.js app, design system tokens and components, top bar, phone bar, API client with mock server from openapi.json",
  "refs": [
    "R-FRONTEND",
    "R-DEVICES",
    "R-SAMPLE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [],
  "gate_ids": [],
  "acceptance": [
    "A-ACCESSIBILITY"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## T-MYWORK — API: My work queues

```json
{
  "id": "T-MYWORK",
  "title": "API: My work queues",
  "refs": [
    "E-WORK-LIST",
    "R-MYWORK",
    "R-VOLUME"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-FOUNDATION"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-MYWORK"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-AUTH, D-WORKLIST-FILTERS

## T-WORKITEM — API: work item and history

```json
{
  "id": "T-WORKITEM",
  "title": "API: work item and history",
  "refs": [
    "E-WORK-ITEM",
    "E-WORK-HISTORY",
    "R-WORKITEM"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-FOUNDATION"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKITEM",
    "A-HISTORY",
    "A-NOT-YOURS"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-AUTH, D-TASK-DECISION-VIEW, D-WORKITEM-DETAIL

## T-DECIDE — API: claim and decide one exact version

```json
{
  "id": "T-DECIDE",
  "title": "API: claim and decide one exact version",
  "refs": [
    "E-TASK-CLAIM",
    "E-TASK-DECIDE",
    "R-DECIDE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-WORKITEM"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-DECIDE",
    "A-STALE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-AUTH, D-TASK-DECISION-VIEW, D-WORKITEM-DETAIL

## T-START — API: lines and start work

```json
{
  "id": "T-START",
  "title": "API: lines and start work",
  "refs": [
    "E-LINES",
    "E-WORK-START",
    "R-START",
    "D-LEADERS-START"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-FOUNDATION"
  ],
  "gate_ids": [
    "D-LEADERS-START"
  ],
  "acceptance": [
    "A-START"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-AUTH

## T-RESPONSE — API: evidence upload and recorded responses

```json
{
  "id": "T-RESPONSE",
  "title": "API: evidence upload and recorded responses",
  "refs": [
    "E-EVIDENCE-UPLOAD",
    "E-RESPONSE",
    "R-RESPONSE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-FOUNDATION"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-RESPONSE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-AUTH

## T-EXCEPTIONS — API: exceptions and work actions

```json
{
  "id": "T-EXCEPTIONS",
  "title": "API: exceptions and work actions",
  "refs": [
    "E-WORK-ACTION",
    "E-EXCEPTIONS",
    "R-EXCEPTION",
    "D-RETURN"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-DECIDE"
  ],
  "gate_ids": [
    "D-RETURN"
  ],
  "acceptance": [
    "A-RECONCILE",
    "A-RESUME"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-AUTH, D-RETURN, D-TASK-DECISION-VIEW, D-WORKITEM-DETAIL

## T-PROJECTS — API: projects, tabs, documents, reports

```json
{
  "id": "T-PROJECTS",
  "title": "API: projects, tabs, documents, reports",
  "refs": [
    "E-PROJECTS",
    "E-PROJECT",
    "E-PROJECT-TAB",
    "E-DOCUMENT",
    "E-REPORT",
    "R-PROJECT",
    "R-REPORTS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-FOUNDATION"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-PROJECT",
    "A-REPORT"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-AUTH

## T-FLOOR — API: overview counts

```json
{
  "id": "T-FLOOR",
  "title": "API: overview counts",
  "refs": [
    "E-OVERVIEW",
    "R-OVERVIEW"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-FOUNDATION"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-OVERVIEW"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-AUTH

## T-FINANCE — API: month-end and imports

```json
{
  "id": "T-FINANCE",
  "title": "API: month-end and imports",
  "refs": [
    "E-MONTH-END",
    "E-IMPORT",
    "R-FINANCE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-FOUNDATION"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-MONTHEND"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-AUTH

## T-PAYROLL — API: payroll match (restricted)

```json
{
  "id": "T-PAYROLL",
  "title": "API: payroll match (restricted)",
  "refs": [
    "E-PAYROLL-MATCH",
    "R-FINANCE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-FOUNDATION"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-PAYROLL"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-AUTH

## T-SETUP — API: rules, people, delegation, templates

```json
{
  "id": "T-SETUP",
  "title": "API: rules, people, delegation, templates",
  "refs": [
    "E-SETUP-RULES",
    "E-SETUP-RULE-SAVE",
    "E-PEOPLE",
    "E-DELEGATION",
    "E-TEMPLATES",
    "R-SETUP"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-FOUNDATION"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-SETUP"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-AUTH

## T-ALERTS — API: notifications and alert preferences (mock adapter)

```json
{
  "id": "T-ALERTS",
  "title": "API: notifications and alert preferences (mock adapter)",
  "refs": [
    "E-NOTIFICATIONS",
    "E-ALERT-PREFS",
    "R-ALERTS",
    "D-ALERT-PROVIDERS",
    "I-ALERTS",
    "JOB-ALERTS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-DECIDE"
  ],
  "gate_ids": [
    "D-ALERT-PROVIDERS"
  ],
  "acceptance": [
    "A-ALERTS"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-ALERT-PROVIDERS, D-API-STYLE, D-AUTH, D-NOTIFY-MODEL, D-TASK-DECISION-VIEW, D-WORKITEM-DETAIL

## T-ASSISTANT — API: assistant conversations

```json
{
  "id": "T-ASSISTANT",
  "title": "API: assistant conversations",
  "refs": [
    "E-CONVERSATION-NEW",
    "E-MESSAGE",
    "E-CONVERSATION",
    "R-ASSISTANT",
    "D-AGENT-PROVIDER",
    "I-AGENT",
    "JOB-ASSISTANT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-START"
  ],
  "gate_ids": [
    "D-AGENT-PROVIDER"
  ],
  "acceptance": [
    "A-ASSISTANT"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-AGENT-PROVIDER, D-API-STYLE, D-AUTH, D-CONVERSATION-MODEL

## T-BACKEND-ROLES — Backend: PMO Lead for Head of PMO, three-step approvals, leaders may start every line

```json
{
  "id": "T-BACKEND-ROLES",
  "title": "Backend: PMO Lead for Head of PMO, three-step approvals, leaders may start every line",
  "refs": [
    "R-ROLES"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [],
  "gate_ids": [],
  "acceptance": [
    "A-START"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-MYWORK — Frontend: My work, three queues, Decide/Do/Fix, search, filter, 10/20/50 rows

```json
{
  "id": "FE-MYWORK",
  "title": "Frontend: My work, three queues, Decide/Do/Fix, search, filter, 10/20/50 rows",
  "refs": [
    "R-MYWORK",
    "R-VOLUME",
    "R-SAMPLE",
    "D-PAGING",
    "D-UPDATES"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [
    "D-PAGING",
    "D-UPDATES"
  ],
  "acceptance": [
    "A-MYWORK"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-WORKITEM — Frontend: work item, stations, facts, agent checklist, history

```json
{
  "id": "FE-WORKITEM",
  "title": "Frontend: work item, stations, facts, agent checklist, history",
  "refs": [
    "R-WORKITEM",
    "D-UPDATES"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [
    "D-UPDATES"
  ],
  "acceptance": [
    "A-WORKITEM",
    "A-HISTORY"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-DECIDE — Frontend: standard decision panel and phone action bar (approve, return, reject; stale-version reload; not yours; own work)

```json
{
  "id": "FE-DECIDE",
  "title": "Frontend: standard decision panel and phone action bar (approve, return, reject; stale-version reload; not yours; own work)",
  "refs": [
    "R-DECIDE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-DECIDE",
    "A-STALE",
    "A-NOT-YOURS"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-DECIDE-VARIANTS — Frontend: payment-exception, CEO final costing and CTO emergency decision variants (parked)

```json
{
  "id": "FE-DECIDE-VARIANTS",
  "title": "Frontend: payment-exception, CEO final costing and CTO emergency decision variants (parked)",
  "refs": [
    "R-DECIDE",
    "D-DECISION-VARIANTS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-DECIDE"
  ],
  "gate_ids": [
    "D-DECISION-VARIANTS"
  ],
  "acceptance": [
    "A-DECIDE-VARIANTS"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-DECISION-VARIANTS

## FE-CONNECT-1 — Connect the first feature to the real API

```json
{
  "id": "FE-CONNECT-1",
  "title": "Connect the first feature to the real API",
  "refs": [
    "R-SESSION",
    "R-MYWORK",
    "R-WORKITEM",
    "R-DECIDE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-MYWORK",
    "FE-WORKITEM",
    "FE-DECIDE",
    "T-FOUNDATION",
    "T-MYWORK",
    "T-WORKITEM",
    "T-DECIDE"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-ME",
    "A-MYWORK",
    "A-WORKITEM",
    "A-DECIDE",
    "A-STALE",
    "A-NOT-YOURS"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-AUTH, D-TASK-DECISION-VIEW, D-WORKITEM-DETAIL, D-WORKLIST-FILTERS

## FE-M2 — Frontend: start work drawers, record a response, exceptions (retired 14 Nov 2026: split into FE-M2A and FE-M2B)

```json
{
  "id": "FE-M2",
  "title": "Frontend: start work drawers, record a response, exceptions (retired 14 Nov 2026: split into FE-M2A and FE-M2B)",
  "refs": [
    "R-START",
    "R-RESPONSE",
    "R-EXCEPTION"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "frontend developer",
  "status": "retired",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-START",
    "A-RESPONSE",
    "A-RECONCILE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-M3 — Frontend: projects, overview and factory floor, Finance, payroll, setup (retired 14 Nov 2026: split into FE-M3-PROJECTS, -OVERVIEW, -FINANCE, -SETUP)

```json
{
  "id": "FE-M3",
  "title": "Frontend: projects, overview and factory floor, Finance, payroll, setup (retired 14 Nov 2026: split into FE-M3-PROJECTS, -OVERVIEW, -FINANCE, -SETUP)",
  "refs": [
    "R-PROJECT",
    "R-REPORTS",
    "R-OVERVIEW",
    "R-MOTION",
    "R-FINANCE",
    "R-SETUP"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "frontend developer",
  "status": "retired",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-PROJECT",
    "A-OVERVIEW",
    "A-MONTHEND",
    "A-PAYROLL",
    "A-SETUP"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-M2A — Frontend: Start work button and line intake drawers

```json
{
  "id": "FE-M2A",
  "title": "Frontend: Start work button and line intake drawers",
  "refs": [
    "R-START"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V4"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-START"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-M2B — Frontend: record a client response and the all-exceptions list

```json
{
  "id": "FE-M2B",
  "title": "Frontend: record a client response and the all-exceptions list",
  "refs": [
    "R-RESPONSE",
    "R-EXCEPTION"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V4"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKITEM"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-RESPONSE",
    "A-RECONCILE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-M3-PROJECTS — Frontend: projects list, project journey and project tabs

```json
{
  "id": "FE-M3-PROJECTS",
  "title": "Frontend: projects list, project journey and project tabs",
  "refs": [
    "R-PROJECT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V4"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-PROJECT"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-M3-OVERVIEW — Frontend: overview, factory floor and reports

```json
{
  "id": "FE-M3-OVERVIEW",
  "title": "Frontend: overview, factory floor and reports",
  "refs": [
    "R-OVERVIEW",
    "R-MOTION",
    "R-REPORTS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V4"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-OVERVIEW"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-M3-FINANCE — Frontend: Finance month end, import and payroll

```json
{
  "id": "FE-M3-FINANCE",
  "title": "Frontend: Finance month end, import and payroll",
  "refs": [
    "R-FINANCE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V4"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-MONTHEND",
    "A-PAYROLL"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-M3-SETUP — Frontend: setup, rules, people and templates

```json
{
  "id": "FE-M3-SETUP",
  "title": "Frontend: setup, rules, people and templates",
  "refs": [
    "R-SETUP"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V4"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-SETUP"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-M4 — Frontend: notification centre, alert settings, assistant

```json
{
  "id": "FE-M4",
  "title": "Frontend: notification centre, alert settings, assistant",
  "refs": [
    "R-ALERTS",
    "R-ASSISTANT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V4"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-ALERTS",
    "A-ASSISTANT"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none
