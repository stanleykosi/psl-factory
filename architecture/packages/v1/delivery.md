# PSL operations factory — frontend and data API — delivery

Dates, assignees and estimates are unassigned unless supported in the canonical model.

## M-1 — First feature: My work and one decision, end to end

```json
{
  "id": "M-1",
  "title": "First feature: My work and one decision, end to end",
  "refs": [
    "T-FOUNDATION",
    "T-FRONTEND-SHELL",
    "T-MYWORK",
    "T-WORKITEM",
    "T-DECIDE",
    "D-FIRST-FEATURE"
  ],
  "evidence": [
    "S-SCREENS"
  ],
  "owner_role": "delivery owner",
  "exit_criteria": [
    "A-ME, A-MYWORK, A-WORKITEM, A-HISTORY, A-DECIDE and A-STALE pass on PostgreSQL with sample data",
    "A-ACCESSIBILITY passes for these screens on phone and desktop",
    "Design review against the approved canvas"
  ],
  "gate_ids": [
    "D-API-STYLE",
    "D-AUTH",
    "D-FIRST-FEATURE"
  ]
}
```

Unresolved gates: D-API-STYLE, D-AUTH, D-FIRST-FEATURE, D-PAGING, D-UPDATES

## M-2 — Start, respond and recover

```json
{
  "id": "M-2",
  "title": "Start, respond and recover",
  "refs": [
    "T-START",
    "T-RESPONSE",
    "T-EXCEPTIONS",
    "T-BACKEND-ROLES"
  ],
  "evidence": [
    "S-SCREENS"
  ],
  "owner_role": "delivery owner",
  "exit_criteria": [
    "A-START, A-RESPONSE, A-RECONCILE, A-RESUME pass"
  ],
  "gate_ids": [
    "D-RETURN"
  ]
}
```

Unresolved gates: D-API-STYLE, D-AUTH, D-PAGING, D-RETURN, D-UPDATES

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
    "T-SETUP"
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

Unresolved gates: D-API-STYLE, D-AUTH, D-PAGING, D-RETURN, D-UPDATES

## M-4 — Alerts and assistant

```json
{
  "id": "M-4",
  "title": "Alerts and assistant",
  "refs": [
    "T-ALERTS",
    "T-ASSISTANT"
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

Unresolved gates: D-AGENT-PROVIDER, D-ALERT-PROVIDERS, D-API-STYLE, D-AUTH, D-CONVERSATION-MODEL, D-NOTIFY-MODEL, D-PAGING, D-UPDATES

## T-FOUNDATION — API foundation: apps/api, session and CSRF, error shape, /me

```json
{
  "id": "T-FOUNDATION",
  "title": "API foundation: apps/api, session and CSRF, error shape, /me",
  "refs": [
    "E-ME",
    "R-SESSION"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "developer",
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

## T-FRONTEND-SHELL — Frontend shell: Next.js app, design system tokens and components, top bar, phone bar

```json
{
  "id": "T-FRONTEND-SHELL",
  "title": "Frontend shell: Next.js app, design system tokens and components, top bar, phone bar",
  "refs": [
    "R-FRONTEND",
    "R-DEVICES",
    "R-SAMPLE",
    "D-AUTH"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "developer",
  "status": "planned",
  "depends_on": [
    "T-FOUNDATION"
  ],
  "gate_ids": [
    "D-AUTH"
  ],
  "acceptance": [
    "A-ACCESSIBILITY"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-AUTH

## T-MYWORK — My work: three queues, Decide/Do/Fix, search and filter

```json
{
  "id": "T-MYWORK",
  "title": "My work: three queues, Decide/Do/Fix, search and filter",
  "refs": [
    "E-WORK-LIST",
    "R-MYWORK",
    "R-VOLUME"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "developer",
  "status": "planned",
  "depends_on": [
    "T-FRONTEND-SHELL"
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

Unresolved gates: D-API-STYLE, D-AUTH, D-PAGING, D-UPDATES

## T-WORKITEM — Work item: stations, facts, agent checklist, history

```json
{
  "id": "T-WORKITEM",
  "title": "Work item: stations, facts, agent checklist, history",
  "refs": [
    "E-WORK-ITEM",
    "E-WORK-HISTORY",
    "R-WORKITEM"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "developer",
  "status": "planned",
  "depends_on": [
    "T-MYWORK"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKITEM",
    "A-HISTORY"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-AUTH, D-PAGING, D-UPDATES

## T-DECIDE — Decisions: claim and decide one exact version, desktop and phone

```json
{
  "id": "T-DECIDE",
  "title": "Decisions: claim and decide one exact version, desktop and phone",
  "refs": [
    "E-TASK-CLAIM",
    "E-TASK-DECIDE",
    "R-DECIDE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "developer",
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

Unresolved gates: D-API-STYLE, D-AUTH, D-PAGING, D-UPDATES

## T-START — Start work: lines menu and every line's intake drawer

```json
{
  "id": "T-START",
  "title": "Start work: lines menu and every line's intake drawer",
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
  "owner_role": "developer",
  "status": "planned",
  "depends_on": [
    "T-WORKITEM"
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

Unresolved gates: D-API-STYLE, D-AUTH, D-PAGING, D-UPDATES

## T-RESPONSE — Record a response with proof

```json
{
  "id": "T-RESPONSE",
  "title": "Record a response with proof",
  "refs": [
    "E-EVIDENCE-UPLOAD",
    "E-RESPONSE",
    "R-RESPONSE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "developer",
  "status": "planned",
  "depends_on": [
    "T-WORKITEM"
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

Unresolved gates: D-API-STYLE, D-AUTH, D-PAGING, D-UPDATES

## T-EXCEPTIONS — Exceptions: reconcile, resume, cancel; All exceptions

```json
{
  "id": "T-EXCEPTIONS",
  "title": "Exceptions: reconcile, resume, cancel; All exceptions",
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
  "owner_role": "developer",
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

Unresolved gates: D-API-STYLE, D-AUTH, D-PAGING, D-RETURN, D-UPDATES

## T-PROJECTS — Projects, project tabs, documents and reports

```json
{
  "id": "T-PROJECTS",
  "title": "Projects, project tabs, documents and reports",
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
  "owner_role": "developer",
  "status": "planned",
  "depends_on": [
    "T-WORKITEM"
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

Unresolved gates: D-API-STYLE, D-AUTH, D-PAGING, D-UPDATES

## T-FLOOR — Overview: factory floor (flat and 3D) with exceptions

```json
{
  "id": "T-FLOOR",
  "title": "Overview: factory floor (flat and 3D) with exceptions",
  "refs": [
    "E-OVERVIEW",
    "R-OVERVIEW",
    "R-MOTION"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "developer",
  "status": "planned",
  "depends_on": [
    "T-EXCEPTIONS"
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

Unresolved gates: D-API-STYLE, D-AUTH, D-PAGING, D-RETURN, D-UPDATES

## T-FINANCE — Finance: month-end, imports and back-office lines

```json
{
  "id": "T-FINANCE",
  "title": "Finance: month-end, imports and back-office lines",
  "refs": [
    "E-MONTH-END",
    "E-IMPORT",
    "R-FINANCE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "developer",
  "status": "planned",
  "depends_on": [
    "T-START"
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

Unresolved gates: D-API-STYLE, D-AUTH, D-PAGING, D-UPDATES

## T-PAYROLL — Payroll (restricted) and HR corrections

```json
{
  "id": "T-PAYROLL",
  "title": "Payroll (restricted) and HR corrections",
  "refs": [
    "E-PAYROLL-MATCH",
    "R-FINANCE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE"
  ],
  "owner_role": "developer",
  "status": "planned",
  "depends_on": [
    "T-FINANCE"
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

Unresolved gates: D-API-STYLE, D-AUTH, D-PAGING, D-UPDATES

## T-SETUP — Setup: rules, people, delegation, templates

```json
{
  "id": "T-SETUP",
  "title": "Setup: rules, people, delegation, templates",
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
  "owner_role": "developer",
  "status": "planned",
  "depends_on": [
    "T-FOUNDATION",
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

Unresolved gates: D-API-STYLE, D-AUTH, D-PAGING

## T-ALERTS — Notifications and alert preferences (mock adapter)

```json
{
  "id": "T-ALERTS",
  "title": "Notifications and alert preferences (mock adapter)",
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
  "owner_role": "developer",
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

Unresolved gates: D-ALERT-PROVIDERS, D-API-STYLE, D-AUTH, D-NOTIFY-MODEL, D-PAGING, D-UPDATES

## T-ASSISTANT — Assistant conversations with sources and drafts

```json
{
  "id": "T-ASSISTANT",
  "title": "Assistant conversations with sources and drafts",
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
  "owner_role": "developer",
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

Unresolved gates: D-AGENT-PROVIDER, D-API-STYLE, D-AUTH, D-CONVERSATION-MODEL, D-PAGING, D-UPDATES

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
  "owner_role": "developer",
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
