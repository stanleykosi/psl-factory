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

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-LINE-WORKSPACE, D-RESPONSE-VIEW, D-RFP-INTAKE, D-RFP-OUTCOME, D-START-INTAKE, D-TASK-DECISION-VIEW, D-WORK-ACTIONS-VIEW, D-WORKITEM-DETAIL, D-WORKLIST-FILTERS

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

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-LINE-WORKSPACE, D-RESPONSE-VIEW, D-RFP-INTAKE, D-RFP-OUTCOME, D-START-INTAKE, D-TASK-DECISION-VIEW, D-WORK-ACTIONS-VIEW, D-WORKITEM-DETAIL, D-WORKLIST-FILTERS

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
    "FE-DECIDE-VARIANTS",
    "FE-M2A-PROOF",
    "FE-M2B-RESPONSE",
    "FE-CONTRACT-V7",
    "FE-M2B-RFP",
    "FE-RFP-INTAKE",
    "T-ASSIGN"
  ],
  "evidence": [
    "S-SCREENS"
  ],
  "owner_role": "delivery owner",
  "exit_criteria": [
    "A-START, A-RESPONSE, A-RECONCILE, A-RESUME pass",
    "A-DECIDE-VARIANTS passes once D-DECISION-VARIANTS is decided",
    "A-START-INTAKE and A-RFP-OUTCOME pass on the contract mock",
    "A-CONTRACT-V7, A-RFP-FOLLOWUP, A-ASSIGN and A-EXCEPTIONS-LIST pass on the v7 contract mock"
  ],
  "gate_ids": [
    "D-RETURN",
    "D-DECISION-VARIANTS"
  ]
}
```

Unresolved gates: D-ALERT-PROVIDERS, D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-DECISION-VARIANTS, D-EXCEPTIONS-LIST, D-LINE-WORKSPACE, D-RESPONSE-VIEW, D-RETURN, D-RFP-INTAKE, D-RFP-OUTCOME, D-START-INTAKE, D-TASK-DECISION-VIEW, D-WORK-ACTIONS-VIEW, D-WORKITEM-DETAIL

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
    "FE-M3-SETUP",
    "FE-M3-PROJECT-TABS",
    "FE-M3-REPORT",
    "T-SETUP-PEOPLE",
    "T-COSTING-RULE",
    "T-CLIENTS",
    "FE-SETUP-DELEGATION",
    "FE-SETUP-ROLES",
    "FE-SETUP-TEMPLATES",
    "FE-SETUP-PAYROLL-FIELDS",
    "FE-SETUP-COSTING",
    "FE-DOCUMENT-REVIEW",
    "FE-MILESTONE-COMPLETE",
    "FE-CLIENTS"
  ],
  "evidence": [
    "S-SCREENS"
  ],
  "owner_role": "delivery owner",
  "exit_criteria": [
    "A-PROJECT, A-REPORT, A-OVERVIEW, A-MONTHEND, A-PAYROLL, A-SETUP pass",
    "A-PROJECT-TABS passes",
    "A-MONTHEND-VIEW, A-SETUP-RULES-VIEW, A-DELEGATIONS, A-TEMPLATE-VERSION, A-PROJECTS-VIEW, A-OVERVIEW-LINES and A-CLIENTS pass",
    "A-PEOPLE-ADMIN, A-PAYROLL-FIELDS and A-COSTING-RULE pass once their decisions are made"
  ],
  "gate_ids": [
    "D-ADMIN-AUTHORITY",
    "D-PAYROLL-VISIBILITY",
    "D-COSTING-RULE"
  ]
}
```

Unresolved gates: D-ADMIN-AUTHORITY, D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-CLIENTS-VIEW, D-COSTING-RULE, D-DELEGATION-VIEW, D-MONTH-END-VIEW, D-OVERVIEW-VIEW, D-PAYROLL-VISIBILITY, D-PEOPLE-VIEW, D-PROJECT-TAB-ROWS, D-PROJECTS-VIEW, D-SETUP-RULES-VIEW, D-SIGNIN, D-START-INTAKE, D-TEMPLATES-VIEW

## M-4 — Alerts and assistant

```json
{
  "id": "M-4",
  "title": "Alerts and assistant",
  "refs": [
    "T-ALERTS",
    "T-ASSISTANT",
    "FE-M4",
    "FE-ALERTS",
    "FE-ALERTS-MENU",
    "FE-ASSISTANT",
    "FE-ASSISTANT-SPEECH"
  ],
  "evidence": [
    "S-SCREENS"
  ],
  "owner_role": "delivery owner",
  "exit_criteria": [
    "A-ALERTS and A-ASSISTANT pass on mock and synthetic providers",
    "A-ALERT-PREFS, A-NOTIFICATIONS and A-ASSISTANT-THREADS pass on the contract mock"
  ],
  "gate_ids": [
    "D-ALERT-PROVIDERS",
    "D-AGENT-PROVIDER",
    "D-NOTIFY-MODEL",
    "D-CONVERSATION-MODEL",
    "D-ALERTS-ENTRY",
    "D-SPEECH-INPUT"
  ]
}
```

Unresolved gates: D-AGENT-PROVIDER, D-ALERT-PREFS-VIEW, D-ALERT-PROVIDERS, D-ALERTS-ENTRY, D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-CONVERSATION-MODEL, D-LINE-WORKSPACE, D-NOTIFY-MODEL, D-RESPONSE-VIEW, D-RFP-INTAKE, D-RFP-OUTCOME, D-SIGNIN, D-SPEECH-INPUT, D-START-INTAKE, D-TASK-DECISION-VIEW, D-WORK-ACTIONS-VIEW, D-WORKITEM-DETAIL

## M-5 — Line workspaces: frame, pre-sale and planning lines

```json
{
  "id": "M-5",
  "title": "Line workspaces: frame, pre-sale and planning lines",
  "refs": [
    "T-WORKSPACE",
    "FE-WORKSPACE-FRAME",
    "FE-RFP-RESPONSE",
    "FE-RFP-SUBMIT",
    "FE-COSTING",
    "FE-ENGAGEMENT-PLANNING"
  ],
  "evidence": [
    "S-SCREENS",
    "S-DECISIONS-V6"
  ],
  "owner_role": "delivery owner",
  "exit_criteria": [
    "A-WORKSPACE passes on PostgreSQL and on the contract mock",
    "Every SCR-26, SCR-40, SCR-41, SCR-42 board passes the design-fidelity check",
    "SCR-27 passes once D-COSTING-RULE is decided"
  ],
  "gate_ids": [
    "D-LINE-WORKSPACE",
    "D-COSTING-RULE"
  ]
}
```

Unresolved gates: D-ALERT-PROVIDERS, D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-COSTING-RULE, D-LINE-WORKSPACE, D-RESPONSE-VIEW, D-RFP-INTAKE, D-RFP-OUTCOME, D-START-INTAKE, D-TASK-DECISION-VIEW, D-WORK-ACTIONS-VIEW, D-WORKITEM-DETAIL

## M-6 — Delivery lines: weekly, minutes, issues, changes, emergencies, escalations, leadership report, release, hypercare, archive, handover and closure

```json
{
  "id": "M-6",
  "title": "Delivery lines: weekly, minutes, issues, changes, emergencies, escalations, leadership report, release, hypercare, archive, handover and closure",
  "refs": [
    "FE-LINE-WEEKLY",
    "FE-LINE-MINUTES",
    "FE-ISSUE",
    "FE-CHANGE",
    "FE-EMERGENCY-ESCALATION",
    "FE-LEADERSHIP-REPORT",
    "FE-DELIVERY-RELEASE",
    "FE-DELIVERY-HYPERCARE-ARCHIVE",
    "FE-DELIVERY-CLOSURE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-DECISIONS-V6"
  ],
  "owner_role": "delivery owner",
  "exit_criteria": [
    "Every board of SCR-25, 28, 30, 31, 33, 43-52 passes the design-fidelity check on the contract mock",
    "SCR-31 decision and authorise pass once D-CHANGE-DECIDERS is decided"
  ],
  "gate_ids": [
    "D-LINE-WORKSPACE",
    "D-CHANGE-DECIDERS",
    "D-DECISION-VARIANTS"
  ]
}
```

Unresolved gates: D-CHANGE-DECIDERS, D-DECISION-VARIANTS, D-LINE-WORKSPACE

## M-7 — Finance lines, payroll, payments and receipts

```json
{
  "id": "M-7",
  "title": "Finance lines, payroll, payments and receipts",
  "refs": [
    "T-RECEIVABLES",
    "FE-FIN-PAYROLL-IMPORT",
    "FE-FIN-PAYROLL-CORRECTIONS",
    "FE-FIN-PAYROLL-RUN",
    "FE-FIN-ACCOUNTS-INTAKE",
    "FE-FIN-ACCOUNTS-PUBLISH",
    "FE-FIN-SCHEDULES",
    "FE-FIN-PPE",
    "FE-FIN-FORECAST",
    "FE-FIN-BU",
    "FE-FIN-LEDGER",
    "FE-PAYMENTS",
    "FE-PAYMENTS-RECEIPT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-DECISIONS-V6"
  ],
  "owner_role": "delivery owner",
  "exit_criteria": [
    "Every Finance canvas board of SCR-09, 18, 20, 32, 37, 53-59 passes the design-fidelity check",
    "A-PAYROLL and A-RECEIVABLES pass; the receipt write once D-RECEIPT-ALLOCATION is decided"
  ],
  "gate_ids": [
    "D-LINE-WORKSPACE",
    "D-RECEIPT-ALLOCATION",
    "D-RETURN",
    "D-DECISION-VARIANTS"
  ]
}
```

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-DECISION-VARIANTS, D-LINE-WORKSPACE, D-MONTH-END-VIEW, D-RECEIPT-ALLOCATION, D-RECEIVABLES-VIEW, D-RETURN, D-START-INTAKE

## M-8 — Sign-in

```json
{
  "id": "M-8",
  "title": "Sign-in",
  "refs": [
    "FE-SIGNIN"
  ],
  "evidence": [
    "S-SCREENS",
    "S-DECISIONS-V6"
  ],
  "owner_role": "delivery owner",
  "exit_criteria": [
    "A-SIGNIN passes once D-SIGNIN is decided"
  ],
  "gate_ids": [
    "D-SIGNIN",
    "D-AUTH"
  ]
}
```

Unresolved gates: D-AUTH, D-SIGNIN

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

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-START-INTAKE

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

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-START-INTAKE, D-WORKLIST-FILTERS

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
    "S-DECISIONS-V6",
    "S-SCOPE",
    "S-SCREENS"
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
    "A-NOT-YOURS",
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-LINE-WORKSPACE, D-RESPONSE-VIEW, D-RFP-INTAKE, D-RFP-OUTCOME, D-START-INTAKE, D-TASK-DECISION-VIEW, D-WORK-ACTIONS-VIEW, D-WORKITEM-DETAIL

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

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-LINE-WORKSPACE, D-RESPONSE-VIEW, D-RFP-INTAKE, D-RFP-OUTCOME, D-START-INTAKE, D-TASK-DECISION-VIEW, D-WORK-ACTIONS-VIEW, D-WORKITEM-DETAIL

## T-START — API: lines and start work

```json
{
  "id": "T-START",
  "title": "API: lines and start work",
  "refs": [
    "E-LINES",
    "E-WORK-START",
    "E-LINE-OPTIONS",
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

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-START-INTAKE

## T-RESPONSE — API: evidence upload and recorded responses

```json
{
  "id": "T-RESPONSE",
  "title": "API: evidence upload and recorded responses",
  "refs": [
    "E-EVIDENCE-UPLOAD",
    "E-RESPONSE",
    "E-RFP-OUTCOME",
    "E-RFP-FOLLOWUP",
    "R-RESPONSE",
    "I-CLIENT-MESSAGES"
  ],
  "evidence": [
    "S-DECISIONS-V6",
    "S-SCOPE",
    "S-SCREENS"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-FOUNDATION"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-RESPONSE",
    "A-RFP-FOLLOWUP",
    "A-RFP-OUTCOME"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-ALERT-PROVIDERS, D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-LINE-WORKSPACE, D-RESPONSE-VIEW, D-RFP-INTAKE, D-RFP-OUTCOME, D-START-INTAKE, D-TASK-DECISION-VIEW, D-WORK-ACTIONS-VIEW, D-WORKITEM-DETAIL

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
    "S-DECISIONS-V6",
    "S-SCOPE",
    "S-SCREENS"
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
    "A-RESUME",
    "A-EXCEPTIONS-LIST"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-EXCEPTIONS-LIST, D-LINE-WORKSPACE, D-RESPONSE-VIEW, D-RETURN, D-RFP-INTAKE, D-RFP-OUTCOME, D-START-INTAKE, D-TASK-DECISION-VIEW, D-WORK-ACTIONS-VIEW, D-WORKITEM-DETAIL

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
    "S-DECISIONS-V6",
    "S-SCOPE",
    "S-SCREENS"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-FOUNDATION"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-PROJECT",
    "A-REPORT",
    "A-PROJECTS-VIEW"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-PROJECT-TAB-ROWS, D-PROJECTS-VIEW, D-START-INTAKE

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
    "S-DECISIONS-V6",
    "S-SCOPE",
    "S-SCREENS"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-FOUNDATION"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-OVERVIEW",
    "A-OVERVIEW-LINES"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-OVERVIEW-VIEW, D-START-INTAKE

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
    "S-DECISIONS-V6",
    "S-SCOPE",
    "S-SCREENS"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-FOUNDATION"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-MONTHEND",
    "A-MONTHEND-VIEW"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-MONTH-END-VIEW, D-START-INTAKE

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

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-START-INTAKE

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
    "E-DELEGATIONS",
    "E-TEMPLATE-VERSION",
    "R-SETUP"
  ],
  "evidence": [
    "S-DECISIONS-V6",
    "S-SCOPE",
    "S-SCREENS"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-FOUNDATION"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-SETUP",
    "A-SETUP-RULES-VIEW",
    "A-DELEGATIONS",
    "A-TEMPLATE-VERSION"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-DELEGATION-VIEW, D-PEOPLE-VIEW, D-SETUP-RULES-VIEW, D-START-INTAKE, D-TEMPLATES-VIEW

## T-ALERTS — API: notifications and alert preferences (mock adapter)

```json
{
  "id": "T-ALERTS",
  "title": "API: notifications and alert preferences (mock adapter)",
  "refs": [
    "E-NOTIFICATIONS",
    "E-ALERT-PREFS",
    "E-ALERT-PREFS-READ",
    "E-NOTIFICATION-READ",
    "R-ALERTS",
    "D-ALERT-PROVIDERS",
    "I-ALERTS",
    "JOB-ALERTS"
  ],
  "evidence": [
    "S-DECISIONS-V6",
    "S-SCOPE",
    "S-SCREENS"
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
    "A-ALERTS",
    "A-ALERT-PREFS",
    "A-NOTIFICATIONS"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-ALERT-PREFS-VIEW, D-ALERT-PROVIDERS, D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-LINE-WORKSPACE, D-NOTIFY-MODEL, D-RESPONSE-VIEW, D-RFP-INTAKE, D-RFP-OUTCOME, D-START-INTAKE, D-TASK-DECISION-VIEW, D-WORK-ACTIONS-VIEW, D-WORKITEM-DETAIL

## T-ASSISTANT — API: assistant conversations

```json
{
  "id": "T-ASSISTANT",
  "title": "API: assistant conversations",
  "refs": [
    "E-CONVERSATION-NEW",
    "E-MESSAGE",
    "E-CONVERSATION",
    "E-CONVERSATIONS",
    "E-MENTION-OPTIONS",
    "R-ASSISTANT",
    "D-AGENT-PROVIDER",
    "I-AGENT",
    "JOB-ASSISTANT"
  ],
  "evidence": [
    "S-DECISIONS-V6",
    "S-SCOPE",
    "S-SCREENS"
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
    "A-ASSISTANT",
    "A-ASSISTANT-THREADS"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-AGENT-PROVIDER, D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-CONVERSATION-MODEL, D-START-INTAKE

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

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-LINE-WORKSPACE, D-RESPONSE-VIEW, D-RFP-INTAKE, D-RFP-OUTCOME, D-START-INTAKE, D-TASK-DECISION-VIEW, D-WORK-ACTIONS-VIEW, D-WORKITEM-DETAIL, D-WORKLIST-FILTERS

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

## FE-M2A — Frontend: core Start work: button, line chooser and intake drawers without proof fields (invoice, weekly, minutes, issue, change, incident, escalation, leadership)

```json
{
  "id": "FE-M2A",
  "title": "Frontend: core Start work: button, line chooser and intake drawers without proof fields (invoice, weekly, minutes, issue, change, incident, escalation, leadership)",
  "refs": [
    "R-START"
  ],
  "evidence": [
    "S-DECISIONS-V4",
    "S-DECISIONS-V5",
    "S-SCOPE",
    "S-SCREENS"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-START",
    "A-START-INTAKE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-M2B — Frontend (F-06): all-exceptions list with search, filter and count (SCR-10)

```json
{
  "id": "FE-M2B",
  "title": "Frontend (F-06): all-exceptions list with search, filter and count (SCR-10)",
  "refs": [
    "R-EXCEPTION"
  ],
  "evidence": [
    "S-DECISIONS-V4",
    "S-DECISIONS-V5",
    "S-DECISIONS-V6",
    "S-SCOPE",
    "S-SCREENS"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKITEM"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-ACCESSIBILITY",
    "A-EXCEPTIONS-LIST"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-M3-PROJECTS — Frontend (F-07): projects list and project journey (SCR-22, SCR-07) with the v7 list and journey fields; tabs in FE-M3-PROJECT-TABS and FE-M3-REPORT

```json
{
  "id": "FE-M3-PROJECTS",
  "title": "Frontend (F-07): projects list and project journey (SCR-22, SCR-07) with the v7 list and journey fields; tabs in FE-M3-PROJECT-TABS and FE-M3-REPORT",
  "refs": [
    "R-PROJECT"
  ],
  "evidence": [
    "S-DECISIONS-V4",
    "S-DECISIONS-V5",
    "S-DECISIONS-V6",
    "S-SCOPE",
    "S-SCREENS"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-PROJECT",
    "A-PROJECTS-VIEW"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-M3-OVERVIEW — Frontend (F-08): overview and factory floor (SCR-06) with line subtitle, agent and status

```json
{
  "id": "FE-M3-OVERVIEW",
  "title": "Frontend (F-08): overview and factory floor (SCR-06) with line subtitle, agent and status",
  "refs": [
    "R-OVERVIEW",
    "R-MOTION",
    "R-REPORTS"
  ],
  "evidence": [
    "S-DECISIONS-V4",
    "S-DECISIONS-V6",
    "S-SCOPE",
    "S-SCREENS"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-OVERVIEW",
    "A-OVERVIEW-LINES"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-M3-FINANCE — Frontend (F-10): Finance month-end checklist (SCR-36); the other Finance screens are FE-FIN-*

```json
{
  "id": "FE-M3-FINANCE",
  "title": "Frontend (F-10): Finance month-end checklist (SCR-36); the other Finance screens are FE-FIN-*",
  "refs": [
    "R-FINANCE"
  ],
  "evidence": [
    "S-DECISIONS-V4",
    "S-DECISIONS-V6",
    "S-SCOPE",
    "S-SCREENS"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-MONTHEND",
    "A-MONTHEND-VIEW"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-M3-SETUP — Frontend (F-11): Setup frame and rule tabs (SCR-13 rules, finance-rules, delivery-rules); other Setup tabs are FE-SETUP-*

```json
{
  "id": "FE-M3-SETUP",
  "title": "Frontend (F-11): Setup frame and rule tabs (SCR-13 rules, finance-rules, delivery-rules); other Setup tabs are FE-SETUP-*",
  "refs": [
    "R-SETUP"
  ],
  "evidence": [
    "S-DECISIONS-V4",
    "S-DECISIONS-V6",
    "S-SCOPE",
    "S-SCREENS"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-SETUP",
    "A-SETUP-RULES-VIEW"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-M4 — Frontend: notification centre, alert settings, assistant (retired 15 Nov 2026: split into FE-ALERTS, FE-ALERTS-MENU, FE-ASSISTANT and FE-ASSISTANT-SPEECH)

```json
{
  "id": "FE-M4",
  "title": "Frontend: notification centre, alert settings, assistant (retired 15 Nov 2026: split into FE-ALERTS, FE-ALERTS-MENU, FE-ASSISTANT and FE-ASSISTANT-SPEECH)",
  "refs": [
    "R-ALERTS",
    "R-ASSISTANT"
  ],
  "evidence": [
    "S-DECISIONS-V4",
    "S-DECISIONS-V6",
    "S-SCOPE",
    "S-SCREENS"
  ],
  "owner_role": "frontend developer",
  "status": "retired",
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

## FE-M2A-PROOF — Frontend: Start work proof fields and the Finance and payroll drawers (accounts, schedules, fixed assets, forecast, BU totals, ledger, payroll restricted)

```json
{
  "id": "FE-M2A-PROOF",
  "title": "Frontend: Start work proof fields and the Finance and payroll drawers (accounts, schedules, fixed assets, forecast, BU totals, ledger, payroll restricted)",
  "refs": [
    "R-START",
    "R-FINANCE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V5"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-M2A",
    "FE-M2B-RESPONSE"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-START-INTAKE",
    "A-PAYROLL"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-M2B-RESPONSE — Frontend (F-09): record a client response or SOW signature (SCR-16 default, validation, success, sow-signed) and reconcile on the work item (SCR-02 awaiting-reconciliation); team input and RFP outcome are FE-M2B-RFP

```json
{
  "id": "FE-M2B-RESPONSE",
  "title": "Frontend (F-09): record a client response or SOW signature (SCR-16 default, validation, success, sow-signed) and reconcile on the work item (SCR-02 awaiting-reconciliation); team input and RFP outcome are FE-M2B-RFP",
  "refs": [
    "R-RESPONSE",
    "R-EXCEPTION"
  ],
  "evidence": [
    "S-DECISIONS-V5",
    "S-DECISIONS-V6",
    "S-SCOPE",
    "S-SCREENS"
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

## FE-M3-PROJECT-TABS — Frontend: project tabs: milestones, documents, registers and actions

```json
{
  "id": "FE-M3-PROJECT-TABS",
  "title": "Frontend: project tabs: milestones, documents, registers and actions",
  "refs": [
    "R-PROJECT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V5"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-M3-PROJECTS"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-PROJECT-TABS"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-M3-REPORT — Frontend: project money tab report with drill-down (SCR-12)

```json
{
  "id": "FE-M3-REPORT",
  "title": "Frontend: project money tab report with drill-down (SCR-12)",
  "refs": [
    "R-PROJECT",
    "R-REPORTS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V5"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-M3-PROJECTS"
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

Unresolved gates: none

## T-WORKSPACE — API: line workspace block on the work item and the line step write

```json
{
  "id": "T-WORKSPACE",
  "title": "API: line workspace block on the work item and the line step write",
  "refs": [
    "E-WORK-STEP",
    "I-CLIENT-MESSAGES",
    "R-WORKITEM",
    "R-FINANCE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-WORKITEM"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-ALERT-PROVIDERS, D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-LINE-WORKSPACE, D-RESPONSE-VIEW, D-RFP-INTAKE, D-RFP-OUTCOME, D-START-INTAKE, D-TASK-DECISION-VIEW, D-WORK-ACTIONS-VIEW, D-WORKITEM-DETAIL

## T-ASSIGN — API: assign the accountable person

```json
{
  "id": "T-ASSIGN",
  "title": "API: assign the accountable person",
  "refs": [
    "E-WORK-ASSIGN",
    "R-START"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-START"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-ASSIGN"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-RFP-INTAKE, D-START-INTAKE

## T-SETUP-PEOPLE — API: role assignment, invite and deactivate (gated)

```json
{
  "id": "T-SETUP-PEOPLE",
  "title": "API: role assignment, invite and deactivate (gated)",
  "refs": [
    "E-PERSON-ROLES",
    "E-INVITE",
    "E-DEACTIVATE",
    "R-SETUP",
    "D-ADMIN-AUTHORITY",
    "D-SIGNIN"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-SETUP"
  ],
  "gate_ids": [
    "D-ADMIN-AUTHORITY",
    "D-SIGNIN"
  ],
  "acceptance": [
    "A-PEOPLE-ADMIN"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-ADMIN-AUTHORITY, D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-DELEGATION-VIEW, D-PEOPLE-VIEW, D-SETUP-RULES-VIEW, D-SIGNIN, D-START-INTAKE, D-TEMPLATES-VIEW

## T-COSTING-RULE — API: costing rule read (writes wait for D-COSTING-RULE)

```json
{
  "id": "T-COSTING-RULE",
  "title": "API: costing rule read (writes wait for D-COSTING-RULE)",
  "refs": [
    "E-COSTING-RULE",
    "R-SETUP",
    "D-COSTING-RULE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-SETUP"
  ],
  "gate_ids": [
    "D-COSTING-RULE"
  ],
  "acceptance": [
    "A-COSTING-RULE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-COSTING-RULE, D-DELEGATION-VIEW, D-PEOPLE-VIEW, D-SETUP-RULES-VIEW, D-START-INTAKE, D-TEMPLATES-VIEW

## T-RECEIVABLES — API: Finance-wide invoices and receipt recording (receipt gated)

```json
{
  "id": "T-RECEIVABLES",
  "title": "API: Finance-wide invoices and receipt recording (receipt gated)",
  "refs": [
    "E-INVOICES",
    "E-RECEIPT",
    "R-FINANCE",
    "D-RECEIPT-ALLOCATION"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-FINANCE"
  ],
  "gate_ids": [
    "D-RECEIPT-ALLOCATION"
  ],
  "acceptance": [
    "A-RECEIVABLES"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-MONTH-END-VIEW, D-RECEIPT-ALLOCATION, D-RECEIVABLES-VIEW, D-START-INTAKE

## T-CLIENTS — API: client register and billing contact

```json
{
  "id": "T-CLIENTS",
  "title": "API: client register and billing contact",
  "refs": [
    "E-CLIENTS",
    "E-CLIENT",
    "E-CLIENT-CONTACT",
    "R-PROJECT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "backend developer",
  "status": "planned",
  "depends_on": [
    "T-PROJECTS"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-CLIENTS"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-API-STYLE, D-ASSISTANT-VIEW, D-AUTH, D-CLIENTS-VIEW, D-PROJECT-TAB-ROWS, D-PROJECTS-VIEW, D-START-INTAKE

## FE-CONTRACT-V7 — Frontend: repoint the frontend contract to v7 and validate all mocks (mock server, gen:api types, drift test, client version comment); one lane owns the repoint

```json
{
  "id": "FE-CONTRACT-V7",
  "title": "Frontend: repoint the frontend contract to v7 and validate all mocks (mock server, gen:api types, drift test, client version comment); one lane owns the repoint",
  "refs": [
    "R-FRONTEND"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-CONTRACT-V7"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-M2B-RFP — Frontend (F-09B): team input and RFP outcome in the RFP frame, with the drafted follow-up (SCR-16 team-input, rfp-outcome, -lost, -pending, -unknown, rfp-won, rfp-lost, rfp-pending, rfp-unknown)

```json
{
  "id": "FE-M2B-RFP",
  "title": "Frontend (F-09B): team input and RFP outcome in the RFP frame, with the drafted follow-up (SCR-16 team-input, rfp-outcome, -lost, -pending, -unknown, rfp-won, rfp-lost, rfp-pending, rfp-unknown)",
  "refs": [
    "R-RESPONSE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-M2B-RESPONSE",
    "FE-CONTRACT-V7"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-RFP-OUTCOME",
    "A-RFP-FOLLOWUP"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-WORKSPACE-FRAME — Frontend: line workspace renderer on the work item (typed sections, step forms from field descriptors, step write with idempotency and uncertain-effect handling)

```json
{
  "id": "FE-WORKSPACE-FRAME",
  "title": "Frontend: line workspace renderer on the work item (typed sections, step forms from field descriptors, step write with idempotency and uncertain-effect handling)",
  "refs": [
    "R-WORKITEM"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKITEM",
    "FE-DECIDE",
    "FE-M2B-RESPONSE",
    "FE-CONTRACT-V7"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-RFP-INTAKE — Frontend: log a received RFP (SCR-23) and assign the accountable PM from Unassigned (SCR-24)

```json
{
  "id": "FE-RFP-INTAKE",
  "title": "Frontend: log a received RFP (SCR-23) and assign the accountable PM from Unassigned (SCR-24)",
  "refs": [
    "R-START"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-M2A",
    "FE-MYWORK",
    "FE-CONTRACT-V7"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-START-INTAKE",
    "A-ASSIGN"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-RFP-RESPONSE — Frontend: RFP response workspace (SCR-26 default, review, edit, accepted, reject, response-review)

```json
{
  "id": "FE-RFP-RESPONSE",
  "title": "Frontend: RFP response workspace (SCR-26 default, review, edit, accepted, reject, response-review)",
  "refs": [
    "R-WORKITEM",
    "R-DECIDE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME",
    "FE-M2B-RFP"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-RFP-SUBMIT — Frontend: RFP submission (SCR-40 draft, review, submitted, submitted-portal)

```json
{
  "id": "FE-RFP-SUBMIT",
  "title": "Frontend: RFP submission (SCR-40 draft, review, submitted, submitted-portal)",
  "refs": [
    "R-WORKITEM",
    "R-DECIDE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME",
    "FE-M2B-RFP"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE",
    "A-RECONCILE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-COSTING — Frontend: costing sheet (SCR-27 default, adjust, ask, approvals); the CEO final decision stays in FE-DECIDE-VARIANTS

```json
{
  "id": "FE-COSTING",
  "title": "Frontend: costing sheet (SCR-27 default, adjust, ask, approvals); the CEO final decision stays in FE-DECIDE-VARIANTS",
  "refs": [
    "R-WORKITEM",
    "R-DECIDE",
    "D-COSTING-RULE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME",
    "FE-SETUP-COSTING"
  ],
  "gate_ids": [
    "D-COSTING-RULE"
  ],
  "acceptance": [
    "A-WORKSPACE",
    "A-COSTING-RULE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-COSTING-RULE

## FE-ENGAGEMENT-PLANNING — Frontend: engagement and planning (SCR-41 default, register; SCR-42 default, record, held, readiness, ready)

```json
{
  "id": "FE-ENGAGEMENT-PLANNING",
  "title": "Frontend: engagement and planning (SCR-41 default, register; SCR-42 default, record, held, readiness, ready)",
  "refs": [
    "R-WORKITEM",
    "R-RESPONSE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE",
    "A-RESPONSE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-LINE-WEEKLY — Frontend: weekly client update (SCR-25 default, invalid, assembling, review, returned, received)

```json
{
  "id": "FE-LINE-WEEKLY",
  "title": "Frontend: weekly client update (SCR-25 default, invalid, assembling, review, returned, received)",
  "refs": [
    "R-WORKITEM",
    "R-DECIDE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-LINE-MINUTES — Frontend: confirm the minutes (SCR-28 default, suggesting, drafted, review, internal, published)

```json
{
  "id": "FE-LINE-MINUTES",
  "title": "Frontend: confirm the minutes (SCR-28 default, suggesting, drafted, review, internal, published)",
  "refs": [
    "R-WORKITEM",
    "R-DECIDE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-ISSUE — Frontend: issue detail (SCR-30 default, overdue, no-owner, verified)

```json
{
  "id": "FE-ISSUE",
  "title": "Frontend: issue detail (SCR-30 default, overdue, no-owner, verified)",
  "refs": [
    "R-WORKITEM"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME",
    "FE-M3-PROJECT-TABS"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-CHANGE — Frontend: change request detail (SCR-31 default, impact, decision, rejected, authorise, notice, execution, go-live-note, closed)

```json
{
  "id": "FE-CHANGE",
  "title": "Frontend: change request detail (SCR-31 default, impact, decision, rejected, authorise, notice, execution, go-live-note, closed)",
  "refs": [
    "R-WORKITEM",
    "R-DECIDE",
    "D-CHANGE-DECIDERS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME",
    "FE-M3-PROJECT-TABS"
  ],
  "gate_ids": [
    "D-CHANGE-DECIDERS"
  ],
  "acceptance": [
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-CHANGE-DECIDERS

## FE-EMERGENCY-ESCALATION — Frontend: emergency change (SCR-50 record, refused, review, retro, report) and escalation (SCR-51 investigating, decide, not-escalated, draft, review, received); the CTO emergency decision stays in FE-DECIDE-VARIANTS

```json
{
  "id": "FE-EMERGENCY-ESCALATION",
  "title": "Frontend: emergency change (SCR-50 record, refused, review, retro, report) and escalation (SCR-51 investigating, decide, not-escalated, draft, review, received); the CTO emergency decision stays in FE-DECIDE-VARIANTS",
  "refs": [
    "R-WORKITEM",
    "R-DECIDE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME",
    "FE-M2A"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-LEADERSHIP-REPORT — Frontend: leadership report (SCR-52 setup, drafting, review, tuesday, received)

```json
{
  "id": "FE-LEADERSHIP-REPORT",
  "title": "Frontend: leadership report (SCR-52 setup, drafting, review, tuesday, received)",
  "refs": [
    "R-WORKITEM",
    "R-REPORTS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME",
    "FE-M3-REPORT"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE",
    "A-REPORT"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-MILESTONE-COMPLETE — Frontend: mark a milestone complete from the Milestones tab (SCR-19), started as the invoice line with proof

```json
{
  "id": "FE-MILESTONE-COMPLETE",
  "title": "Frontend: mark a milestone complete from the Milestones tab (SCR-19), started as the invoice line with proof",
  "refs": [
    "R-START",
    "R-PROJECT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-M3-PROJECT-TABS",
    "FE-M2A-PROOF"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-START-INTAKE",
    "A-PROJECT-TABS"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-DOCUMENT-REVIEW — Frontend: document review page (SCR-08 default, returned)

```json
{
  "id": "FE-DOCUMENT-REVIEW",
  "title": "Frontend: document review page (SCR-08 default, returned)",
  "refs": [
    "R-PROJECT",
    "R-DECIDE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-M3-PROJECT-TABS",
    "FE-DECIDE"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-PROJECT-TABS",
    "A-DECIDE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-DELIVERY-RELEASE — Frontend: delivery overview (SCR-43), release gates (SCR-44 default, decision, returned, owner-needed, readiness, ready) and go-live acceptance (SCR-45 default, signatures, accepted, changes, declined)

```json
{
  "id": "FE-DELIVERY-RELEASE",
  "title": "Frontend: delivery overview (SCR-43), release gates (SCR-44 default, decision, returned, owner-needed, readiness, ready) and go-live acceptance (SCR-45 default, signatures, accepted, changes, declined)",
  "refs": [
    "R-PROJECT",
    "R-WORKITEM",
    "R-RESPONSE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME",
    "FE-M3-PROJECTS"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE",
    "A-PROJECTS-VIEW",
    "A-RESPONSE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-DELIVERY-HYPERCARE-ARCHIVE — Frontend: hypercare (SCR-46 default, record, evaluating, qualified, not-met, setup-needed) and archive (SCR-47 default, working, uncertain)

```json
{
  "id": "FE-DELIVERY-HYPERCARE-ARCHIVE",
  "title": "Frontend: hypercare (SCR-46 default, record, evaluating, qualified, not-met, setup-needed) and archive (SCR-47 default, working, uncertain)",
  "refs": [
    "R-WORKITEM",
    "R-EXCEPTION"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE",
    "A-RECONCILE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-DELIVERY-CLOSURE — Frontend: handover to Support (SCR-48 default, record, gaps, received), closure (SCR-49 default, blocked, decision, returned, closed) and the retrospective (SCR-33)

```json
{
  "id": "FE-DELIVERY-CLOSURE",
  "title": "Frontend: handover to Support (SCR-48 default, record, gaps, received), closure (SCR-49 default, blocked, decision, returned, closed) and the retrospective (SCR-33)",
  "refs": [
    "R-WORKITEM",
    "R-DECIDE",
    "R-RESPONSE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE",
    "A-RESPONSE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-PAYMENTS — Frontend: payments and follow-up list (SCR-20 default) and the payment reminder (SCR-32); the short payment stays in FE-DECIDE-VARIANTS

```json
{
  "id": "FE-PAYMENTS",
  "title": "Frontend: payments and follow-up list (SCR-20 default) and the payment reminder (SCR-32); the short payment stays in FE-DECIDE-VARIANTS",
  "refs": [
    "R-FINANCE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-RECEIVABLES",
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-PAYMENTS-RECEIPT — Frontend: record a payment (SCR-20 record), gated until the allocation rule is decided

```json
{
  "id": "FE-PAYMENTS-RECEIPT",
  "title": "Frontend: record a payment (SCR-20 record), gated until the allocation rule is decided",
  "refs": [
    "R-FINANCE",
    "D-RECEIPT-ALLOCATION"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-PAYMENTS"
  ],
  "gate_ids": [
    "D-RECEIPT-ALLOCATION"
  ],
  "acceptance": [
    "A-RECEIVABLES"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-RECEIPT-ALLOCATION

## FE-CLIENTS — Frontend: clients and client detail with the billing contact (SCR-35 default, detail)

```json
{
  "id": "FE-CLIENTS",
  "title": "Frontend: clients and client detail with the billing contact (SCR-35 default, detail)",
  "refs": [
    "R-PROJECT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-M3-PROJECTS",
    "FE-CONTRACT-V7"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-CLIENTS"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-SIGNIN — Frontend: sign in, error, reset and account set-up (SCR-17), gated until sign-in is decided

```json
{
  "id": "FE-SIGNIN",
  "title": "Frontend: sign in, error, reset and account set-up (SCR-17), gated until sign-in is decided",
  "refs": [
    "R-SESSION",
    "D-SIGNIN"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "T-FRONTEND-SHELL"
  ],
  "gate_ids": [
    "D-SIGNIN"
  ],
  "acceptance": [
    "A-SIGNIN"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-AUTH, D-SIGNIN

## FE-FIN-PAYROLL-IMPORT — Frontend (F-10B): payroll inputs and restricted matching (SCR-09 default, error; SCR-18 default, permission)

```json
{
  "id": "FE-FIN-PAYROLL-IMPORT",
  "title": "Frontend (F-10B): payroll inputs and restricted matching (SCR-09 default, error; SCR-18 default, permission)",
  "refs": [
    "R-FINANCE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-PAYROLL",
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-FIN-PAYROLL-CORRECTIONS — Frontend (F-10C): payroll corrections and the HR Lead decision (SCR-37)

```json
{
  "id": "FE-FIN-PAYROLL-CORRECTIONS",
  "title": "Frontend (F-10C): payroll corrections and the HR Lead decision (SCR-37)",
  "refs": [
    "R-FINANCE",
    "R-DECIDE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-PAYROLL",
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-FIN-PAYROLL-RUN — Frontend (F-10D): payroll run (SCR-59 input-review, combine-review, match-held, match-review, totals-review, publish, receipts, verified, followup)

```json
{
  "id": "FE-FIN-PAYROLL-RUN",
  "title": "Frontend (F-10D): payroll run (SCR-59 input-review, combine-review, match-held, match-review, totals-review, publish, receipts, verified, followup)",
  "refs": [
    "R-FINANCE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-FIN-PAYROLL-IMPORT"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-PAYROLL",
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-FIN-ACCOUNTS-INTAKE — Frontend (F-10E1): management accounts intake and investigation (SCR-53 quarantined, units, investigating, owner-needed, setup-needed, returned)

```json
{
  "id": "FE-FIN-ACCOUNTS-INTAKE",
  "title": "Frontend (F-10E1): management accounts intake and investigation (SCR-53 quarantined, units, investigating, owner-needed, setup-needed, returned)",
  "refs": [
    "R-FINANCE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME",
    "FE-M2A-PROOF"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-MONTHEND",
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-FIN-ACCOUNTS-PUBLISH — Frontend (F-10E2): management accounts reviews and publication (SCR-53 reviews, drafting, publishing, uncertain, verified)

```json
{
  "id": "FE-FIN-ACCOUNTS-PUBLISH",
  "title": "Frontend (F-10E2): management accounts reviews and publication (SCR-53 reviews, drafting, publishing, uncertain, verified)",
  "refs": [
    "R-FINANCE",
    "R-DECIDE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-FIN-ACCOUNTS-INTAKE",
    "FE-M3-FINANCE"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE",
    "A-RECONCILE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-FIN-SCHEDULES — Frontend (F-10F): income detail and schedules (SCR-54 investigating, held, review, returned, verified, export, withdrawn)

```json
{
  "id": "FE-FIN-SCHEDULES",
  "title": "Frontend (F-10F): income detail and schedules (SCR-54 investigating, held, review, returned, verified, export, withdrawn)",
  "refs": [
    "R-FINANCE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-FIN-PPE — Frontend (F-10G): fixed asset schedule (SCR-55 investigating, register-review, date-review, calculating, schedule-review, returned, verified)

```json
{
  "id": "FE-FIN-PPE",
  "title": "Frontend (F-10G): fixed asset schedule (SCR-55 investigating, register-review, date-review, calculating, schedule-review, returned, verified)",
  "refs": [
    "R-FINANCE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-FIN-FORECAST — Frontend (F-10H): cash forecast and actuals (SCR-56 investigating, review, group-rows, group-review, uncertain, verified, actuals)

```json
{
  "id": "FE-FIN-FORECAST",
  "title": "Frontend (F-10H): cash forecast and actuals (SCR-56 investigating, review, group-rows, group-review, uncertain, verified, actuals)",
  "refs": [
    "R-FINANCE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-FIN-BU — Frontend (F-10I): business-unit totals (SCR-57 source-review, investigating, held, result-review, publish, receipts, verified)

```json
{
  "id": "FE-FIN-BU",
  "title": "Frontend (F-10I): business-unit totals (SCR-57 source-review, investigating, held, result-review, publish, receipts, verified)",
  "refs": [
    "R-FINANCE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-FIN-LEDGER — Frontend (F-10J): ledger source reference (SCR-58 investigating, duplicate, observe, review, rejected, verified)

```json
{
  "id": "FE-FIN-LEDGER",
  "title": "Frontend (F-10J): ledger source reference (SCR-58 investigating, duplicate, observe, review, rejected, verified)",
  "refs": [
    "R-FINANCE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-WORKSPACE-FRAME"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-WORKSPACE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-SETUP-DELEGATION — Frontend (F-11B): delegation tab (SCR-13 delegation)

```json
{
  "id": "FE-SETUP-DELEGATION",
  "title": "Frontend (F-11B): delegation tab (SCR-13 delegation)",
  "refs": [
    "R-SETUP"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-M3-SETUP",
    "FE-CONTRACT-V7"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-DELEGATIONS"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-SETUP-ROLES — Frontend (F-11C): roles and staff accounts (SCR-13 default, permission, validation; SCR-21 default, invite, deactivate), gated until PSL names who holds Admin

```json
{
  "id": "FE-SETUP-ROLES",
  "title": "Frontend (F-11C): roles and staff accounts (SCR-13 default, permission, validation; SCR-21 default, invite, deactivate), gated until PSL names who holds Admin",
  "refs": [
    "R-SETUP",
    "D-ADMIN-AUTHORITY"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-M3-SETUP",
    "FE-CONTRACT-V7"
  ],
  "gate_ids": [
    "D-ADMIN-AUTHORITY"
  ],
  "acceptance": [
    "A-PEOPLE-ADMIN"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-ADMIN-AUTHORITY

## FE-SETUP-TEMPLATES — Frontend (F-11D): templates with versioned upload (SCR-34)

```json
{
  "id": "FE-SETUP-TEMPLATES",
  "title": "Frontend (F-11D): templates with versioned upload (SCR-34)",
  "refs": [
    "R-SETUP"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-M3-SETUP",
    "FE-CONTRACT-V7"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-TEMPLATE-VERSION"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-SETUP-PAYROLL-FIELDS — Frontend (F-11E): payroll field visibility (SCR-13 fields), gated until PSL decides it

```json
{
  "id": "FE-SETUP-PAYROLL-FIELDS",
  "title": "Frontend (F-11E): payroll field visibility (SCR-13 fields), gated until PSL decides it",
  "refs": [
    "R-SETUP",
    "D-PAYROLL-VISIBILITY"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-M3-SETUP",
    "FE-CONTRACT-V7"
  ],
  "gate_ids": [
    "D-PAYROLL-VISIBILITY"
  ],
  "acceptance": [
    "A-PAYROLL-FIELDS"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-PAYROLL-VISIBILITY

## FE-SETUP-COSTING — Frontend (F-11F): costing rule (SCR-39 default, review, example, review-own), gated until the rule is decided

```json
{
  "id": "FE-SETUP-COSTING",
  "title": "Frontend (F-11F): costing rule (SCR-39 default, review, example, review-own), gated until the rule is decided",
  "refs": [
    "R-SETUP",
    "D-COSTING-RULE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-M3-SETUP",
    "FE-CONTRACT-V7"
  ],
  "gate_ids": [
    "D-COSTING-RULE"
  ],
  "acceptance": [
    "A-COSTING-RULE"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-COSTING-RULE

## FE-ALERTS — Frontend (F-12A): notification centre and alert settings (SCR-15 default, settings; STATES); the WhatsApp and email boards are T-ALERTS message content

```json
{
  "id": "FE-ALERTS",
  "title": "Frontend (F-12A): notification centre and alert settings (SCR-15 default, settings; STATES); the WhatsApp and email boards are T-ALERTS message content",
  "refs": [
    "R-ALERTS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-CONTRACT-V7"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-ALERTS",
    "A-ALERT-PREFS",
    "A-NOTIFICATIONS"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-ALERTS-MENU — Frontend (F-12A2): bell and account menu in the top bar (SCR-15 account), gated on where the bell is drawn and on sign-out

```json
{
  "id": "FE-ALERTS-MENU",
  "title": "Frontend (F-12A2): bell and account menu in the top bar (SCR-15 account), gated on where the bell is drawn and on sign-out",
  "refs": [
    "R-ALERTS",
    "R-SESSION",
    "D-ALERTS-ENTRY",
    "D-SIGNIN"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-ALERTS",
    "FE-M2A"
  ],
  "gate_ids": [
    "D-ALERTS-ENTRY",
    "D-SIGNIN"
  ],
  "acceptance": [
    "A-NOTIFICATIONS"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-ALERTS-ENTRY, D-AUTH, D-SIGNIN

## FE-ASSISTANT — Frontend (F-12B): assistant (SCR-05 default, thread, draft-started, cant, working) without speech input

```json
{
  "id": "FE-ASSISTANT",
  "title": "Frontend (F-12B): assistant (SCR-05 default, thread, draft-started, cant, working) without speech input",
  "refs": [
    "R-ASSISTANT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-CONTRACT-V7",
    "FE-M2A"
  ],
  "gate_ids": [],
  "acceptance": [
    "A-ASSISTANT",
    "A-ASSISTANT-THREADS"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: none

## FE-ASSISTANT-SPEECH — Frontend: "Speak your request" in the assistant composer (SCR-05), gated on D-SPEECH-INPUT

```json
{
  "id": "FE-ASSISTANT-SPEECH",
  "title": "Frontend: \"Speak your request\" in the assistant composer (SCR-05), gated on D-SPEECH-INPUT",
  "refs": [
    "R-ASSISTANT",
    "D-SPEECH-INPUT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-SCOPE",
    "S-DECISIONS-V6"
  ],
  "owner_role": "frontend developer",
  "status": "planned",
  "depends_on": [
    "FE-ASSISTANT"
  ],
  "gate_ids": [
    "D-SPEECH-INPUT"
  ],
  "acceptance": [
    "A-SPEECH-INPUT"
  ],
  "estimate": null,
  "assignee": null,
  "due_date": null
}
```

Unresolved gates: D-SPEECH-INPUT
