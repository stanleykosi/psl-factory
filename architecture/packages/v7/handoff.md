# PSL operations factory — frontend and data API — developer handoff

Scope v2: new Next.js frontend in frontend/ on a data API added to the existing Django backend (S-08, I-02).

Artifact validation passed. Application/integration acceptance was not executed by the generator.

## Architecture and logical data

## Components

### C-STAFF — PSL staff (PMO, Finance, HR, Leads, CEO, CTO)

```json
{
  "id": "C-STAFF",
  "title": "PSL staff (PMO, Finance, HR, Leads, CEO, CTO)",
  "refs": [],
  "evidence": [
    "S-SCOPE"
  ],
  "kind": "actor",
  "trust_boundary": "Untrusted browser or phone",
  "responsibilities": "Use the factory through the frontend; sign in once.",
  "owner": "operator"
}
```

### C-FRONTEND — Next.js frontend (frontend/)

```json
{
  "id": "C-FRONTEND",
  "title": "Next.js frontend (frontend/)",
  "refs": [],
  "evidence": [
    "S-SCOPE",
    "S-SCREENS"
  ],
  "kind": "application",
  "trust_boundary": "Untrusted browser; same-origin",
  "responsibilities": "Render the approved screens with the design system, GSAP motion and the three.js floor; call /api/v1 only; hold no business rules.",
  "owner": "developer"
}
```

### C-API — Data API (apps/api, /api/v1)

```json
{
  "id": "C-API",
  "title": "Data API (apps/api, /api/v1)",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "kind": "module",
  "trust_boundary": "Django application boundary; session + CSRF",
  "responsibilities": "Translate requests to existing service calls; check grants per record and action; shape JSON for screens.",
  "owner": "developer"
}
```

### C-SERVICES — Domain services (workflows, pmo, finance, documents, identity, policy)

```json
{
  "id": "C-SERVICES",
  "title": "Domain services (workflows, pmo, finance, documents, identity, policy)",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "kind": "module",
  "trust_boundary": "Django application boundary",
  "responsibilities": "Own every business rule, revision check, approval and audit event.",
  "owner": "developer"
}
```

### C-WORKERS — Job workers (work_* commands)

```json
{
  "id": "C-WORKERS",
  "title": "Job workers (work_* commands)",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "kind": "application",
  "trust_boundary": "Private server",
  "responsibilities": "Run factory steps, agent work, publications and the outbox from leased job tables.",
  "owner": "developer"
}
```

### C-DB — PostgreSQL

```json
{
  "id": "C-DB",
  "title": "PostgreSQL",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "kind": "store",
  "trust_boundary": "Private persistence",
  "responsibilities": "Records, append-only audit, job tables.",
  "owner": "developer"
}
```

### C-ALERTS — Alert adapter (mock until providers chosen)

```json
{
  "id": "C-ALERTS",
  "title": "Alert adapter (mock until providers chosen)",
  "refs": [],
  "evidence": [
    "S-SCOPE"
  ],
  "kind": "module",
  "trust_boundary": "Private server; provider secrets server-only",
  "responsibilities": "Send WhatsApp and email alerts from the outbox; record receipts and uncertain sends.",
  "owner": "developer"
}
```

### C-AGENTS — Agent coordinator (Tola, Chidi, Zainab)

```json
{
  "id": "C-AGENTS",
  "title": "Agent coordinator (Tola, Chidi, Zainab)",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "kind": "module",
  "trust_boundary": "Private server; provider credentials server-only",
  "responsibilities": "Run agent steps and assistant answers on records the requester may see; never approve, send or pay.",
  "owner": "developer"
}
```

## Views

### V-CONTEXT — System context

```json
{
  "id": "V-CONTEXT",
  "title": "System context",
  "refs": [
    "C-STAFF",
    "C-FRONTEND",
    "C-API"
  ],
  "evidence": [
    "S-BACKEND",
    "S-SCOPE"
  ],
  "kind": "context",
  "nodes": [
    "C-STAFF",
    "C-FRONTEND",
    "C-API"
  ],
  "edges": [
    {
      "from": "C-STAFF",
      "to": "C-FRONTEND",
      "label": "Browser or phone"
    },
    {
      "from": "C-FRONTEND",
      "to": "C-API",
      "label": "JSON over same-origin session"
    }
  ],
  "notes": "People who do not log in are recorded by PMO (U-09)."
}
```

### V-APP — Applications and stores

```json
{
  "id": "V-APP",
  "title": "Applications and stores",
  "refs": [
    "C-FRONTEND",
    "C-API",
    "C-SERVICES",
    "C-WORKERS",
    "C-DB"
  ],
  "evidence": [
    "S-BACKEND",
    "S-SCOPE"
  ],
  "kind": "application",
  "nodes": [
    "C-FRONTEND",
    "C-API",
    "C-SERVICES",
    "C-WORKERS",
    "C-DB"
  ],
  "edges": [
    {
      "from": "C-FRONTEND",
      "to": "C-API",
      "label": "/api/v1"
    },
    {
      "from": "C-API",
      "to": "C-SERVICES",
      "label": "service calls with expected revision"
    },
    {
      "from": "C-SERVICES",
      "to": "C-DB",
      "label": "records + audit"
    },
    {
      "from": "C-WORKERS",
      "to": "C-DB",
      "label": "leased jobs"
    }
  ],
  "notes": "Business rules stay in services (C-05)."
}
```

### V-MODULE — API module

```json
{
  "id": "V-MODULE",
  "title": "API module",
  "refs": [
    "C-API",
    "C-SERVICES",
    "C-AGENTS",
    "C-ALERTS"
  ],
  "evidence": [
    "S-BACKEND",
    "S-SCOPE"
  ],
  "kind": "module",
  "nodes": [
    "C-API",
    "C-SERVICES",
    "C-AGENTS",
    "C-ALERTS"
  ],
  "edges": [
    {
      "from": "C-API",
      "to": "C-SERVICES",
      "label": "grants and authority checks"
    },
    {
      "from": "C-SERVICES",
      "to": "C-AGENTS",
      "label": "agent runs"
    },
    {
      "from": "C-SERVICES",
      "to": "C-ALERTS",
      "label": "outbox"
    }
  ],
  "notes": "apps/api is new; no business logic in it."
}
```

### V-DEPLOY — Logical deployment

```json
{
  "id": "V-DEPLOY",
  "title": "Logical deployment",
  "refs": [
    "C-FRONTEND",
    "C-API",
    "C-DB",
    "C-WORKERS"
  ],
  "evidence": [
    "S-BACKEND",
    "S-SCOPE"
  ],
  "kind": "deployment",
  "nodes": [
    "C-FRONTEND",
    "C-API",
    "C-DB",
    "C-WORKERS"
  ],
  "edges": [
    {
      "from": "C-FRONTEND",
      "to": "C-API",
      "label": "same host, /api/v1 proxied"
    },
    {
      "from": "C-API",
      "to": "C-DB",
      "label": "private network"
    }
  ],
  "notes": "Hosting is open (D-HOSTING)."
}
```

### V-DATA — Records

```json
{
  "id": "V-DATA",
  "title": "Records",
  "refs": [
    "REC-CASE",
    "REC-WORK",
    "REC-TASK",
    "REC-AUDIT",
    "REC-NOTIFICATION",
    "REC-CONVERSATION",
    "REC-CLIENT"
  ],
  "evidence": [
    "S-BACKEND",
    "S-SCOPE"
  ],
  "kind": "data",
  "nodes": [
    "REC-CASE",
    "REC-WORK",
    "REC-TASK",
    "REC-AUDIT",
    "REC-NOTIFICATION",
    "REC-CONVERSATION",
    "REC-CLIENT"
  ],
  "edges": [
    {
      "from": "REC-WORK",
      "to": "REC-CASE",
      "label": "belongs to"
    },
    {
      "from": "REC-TASK",
      "to": "REC-WORK",
      "label": "belongs to"
    },
    {
      "from": "REC-AUDIT",
      "to": "REC-CASE",
      "label": "history of"
    },
    {
      "from": "REC-CLIENT",
      "to": "REC-CASE",
      "label": "has cases (proposed)"
    }
  ],
  "notes": "New records: notification, alert preference, conversation. v7 proposes REC-CLIENT (client and billing contact)."
}
```

## Records

### REC-CASE — Case (project or support)

```json
{
  "id": "REC-CASE",
  "title": "Case (project or support)",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "fields": [
    "id: uuid",
    "kind: project|support",
    "title",
    "revision"
  ],
  "relationships": [],
  "constraints": [
    "Visible only with a case.read grant"
  ],
  "owner": "core"
}
```

### REC-GRANT — Grant (case, user, action)

```json
{
  "id": "REC-GRANT",
  "title": "Grant (case, user, action)",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "fields": [
    "case",
    "user",
    "action",
    "active"
  ],
  "relationships": [
    "REC-CASE"
  ],
  "constraints": [
    "UNIQUE(case, user, action) while active"
  ],
  "owner": "identity"
}
```

### REC-WORK — Factory work item

```json
{
  "id": "REC-WORK",
  "title": "Factory work item",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "fields": [
    "id",
    "case",
    "key",
    "definition (line/version)",
    "request",
    "status",
    "revision",
    "cancel_requested"
  ],
  "relationships": [
    "REC-CASE"
  ],
  "constraints": [
    "revision increases on every change",
    "status in the factory state set"
  ],
  "owner": "workflows"
}
```

### REC-TASK — Human task (decision or recording)

```json
{
  "id": "REC-TASK",
  "title": "Human task (decision or recording)",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "fields": [
    "id",
    "factory_key",
    "kind",
    "required_role",
    "claimed_by",
    "revision",
    "status"
  ],
  "relationships": [
    "REC-WORK"
  ],
  "constraints": [
    "A decision names one exact document version",
    "Preparer cannot decide own work where separation applies"
  ],
  "owner": "workflows"
}
```

### REC-EVIDENCE — Evidence (proof, response, upload)

```json
{
  "id": "REC-EVIDENCE",
  "title": "Evidence (proof, response, upload)",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "fields": [
    "id",
    "case",
    "kind",
    "body",
    "source",
    "sha256"
  ],
  "relationships": [
    "REC-CASE"
  ],
  "constraints": [
    "Append-only"
  ],
  "owner": "core"
}
```

### REC-AUDIT — Audit event

```json
{
  "id": "REC-AUDIT",
  "title": "Audit event",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "fields": [
    "id",
    "case",
    "actor",
    "action",
    "at",
    "detail"
  ],
  "relationships": [
    "REC-CASE"
  ],
  "constraints": [
    "Append-only; corrections are new events"
  ],
  "owner": "core"
}
```

### REC-AGENTRUN — Agent run

```json
{
  "id": "REC-AGENTRUN",
  "title": "Agent run",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "fields": [
    "id",
    "agent",
    "work",
    "steps",
    "records_read",
    "status"
  ],
  "relationships": [
    "REC-WORK"
  ],
  "constraints": [
    "Never records an approval"
  ],
  "owner": "agents"
}
```

### REC-DOCUMENT — Document and version

```json
{
  "id": "REC-DOCUMENT",
  "title": "Document and version",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "fields": [
    "id",
    "case",
    "template",
    "version",
    "status"
  ],
  "relationships": [
    "REC-CASE"
  ],
  "constraints": [
    "Decisions bind to a version"
  ],
  "owner": "documents"
}
```

### REC-MONEY — Invoice, receipt and allocation

```json
{
  "id": "REC-MONEY",
  "title": "Invoice, receipt and allocation",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "fields": [
    "invoice: amount, status, issue, delivery",
    "receipt: amount, date",
    "allocation"
  ],
  "relationships": [
    "REC-CASE"
  ],
  "constraints": [
    "Stages, invoices, receipts and allocations are separate",
    "Unknown amounts are not zero"
  ],
  "owner": "finance"
}
```

### REC-CONFIG — Versioned configuration (rules)

```json
{
  "id": "REC-CONFIG",
  "title": "Versioned configuration (rules)",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "fields": [
    "case",
    "component",
    "revision",
    "envelope"
  ],
  "relationships": [
    "REC-CASE"
  ],
  "constraints": [
    "A missing value is Not set, never a default"
  ],
  "owner": "policy"
}
```

### REC-NOTIFICATION — Notification (new)

```json
{
  "id": "REC-NOTIFICATION",
  "title": "Notification (new)",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "fields": [
    "id",
    "person",
    "work",
    "event",
    "created_at",
    "read_at",
    "channel_status"
  ],
  "relationships": [
    "REC-WORK"
  ],
  "constraints": [
    "One per person per event",
    "Carries no amounts or client details"
  ],
  "owner": "apps/api (new)"
}
```

### REC-ALERT-PREF — Alert preference (new)

```json
{
  "id": "REC-ALERT-PREF",
  "title": "Alert preference (new)",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "fields": [
    "person",
    "channel: whatsapp|email|both|none",
    "frequency: immediate|daily"
  ],
  "relationships": [],
  "constraints": [
    "One per person"
  ],
  "owner": "apps/api (new)"
}
```

### REC-CONVERSATION — Assistant conversation and message (new)

```json
{
  "id": "REC-CONVERSATION",
  "title": "Assistant conversation and message (new)",
  "refs": [],
  "evidence": [
    "S-BACKEND"
  ],
  "fields": [
    "id",
    "person",
    "messages: role, text, sources[], agent_run"
  ],
  "relationships": [
    "REC-AGENTRUN"
  ],
  "constraints": [
    "Every assistant message lists its sources",
    "Drafts link to a started work item, never a finished one"
  ],
  "owner": "agents (new)"
}
```

### REC-CLIENT — Client and billing contact (proposed; backend developer to confirm where it lives)

```json
{
  "id": "REC-CLIENT",
  "title": "Client and billing contact (proposed; backend developer to confirm where it lives)",
  "refs": [
    "REC-CASE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-DECISIONS-V6"
  ],
  "fields": [
    "id",
    "name",
    "billing_contact: name, email",
    "revision"
  ],
  "relationships": [
    "REC-CASE"
  ],
  "constraints": [
    "An invoice is not sent without a billing contact (as SCR-35 states; the backend holds the rule)",
    "Visible only through a case the person may read"
  ],
  "owner": "pmo (backend developer to confirm)"
}
```

## Invariants

### INV-ACCESS — Every record and action is checked by the backend

```json
{
  "id": "INV-ACCESS",
  "title": "Every record and action is checked by the backend",
  "refs": [
    "REC-GRANT",
    "A-ME",
    "A-MYWORK",
    "A-PAYROLL"
  ],
  "evidence": [
    "S-SCOPE",
    "S-BACKEND"
  ],
  "rule": "Each endpoint resolves the case and calls require(actor, case, action) or the line's authority check before reading or writing; lists filter by grants.",
  "scope": "All endpoints"
}
```

### INV-REVISION — Act only on the current version

```json
{
  "id": "INV-REVISION",
  "title": "Act only on the current version",
  "refs": [
    "REC-WORK",
    "REC-TASK",
    "A-STALE",
    "A-SETUP"
  ],
  "evidence": [
    "S-SCOPE",
    "S-BACKEND"
  ],
  "rule": "Writes carry expected_revision; a mismatch returns 409 and changes nothing.",
  "scope": "All writes"
}
```

### INV-FACTS — Facts are never merged

```json
{
  "id": "INV-FACTS",
  "title": "Facts are never merged",
  "refs": [
    "REC-WORK",
    "REC-MONEY",
    "A-WORKITEM",
    "A-PROJECT"
  ],
  "evidence": [
    "S-SCOPE",
    "S-BACKEND"
  ],
  "rule": "Payloads return drafted, reviewed, approved, sent, receipt recorded and verified as separate facts; paid is separate Finance data.",
  "scope": "Work item, money"
}
```

### INV-UNKNOWN — Unknown is not zero

```json
{
  "id": "INV-UNKNOWN",
  "title": "Unknown is not zero",
  "refs": [
    "REC-MONEY",
    "A-WORKITEM",
    "A-MONTHEND",
    "A-REPORT"
  ],
  "evidence": [
    "S-SCOPE",
    "S-BACKEND"
  ],
  "rule": "Amounts and dates that are not known are returned with unknown=true and no value.",
  "scope": "All payloads with amounts or dates"
}
```

### INV-AGENT — Agents never decide

```json
{
  "id": "INV-AGENT",
  "title": "Agents never decide",
  "refs": [
    "REC-AGENTRUN",
    "REC-TASK",
    "A-WORKITEM",
    "A-ASSISTANT"
  ],
  "evidence": [
    "S-SCOPE",
    "S-BACKEND"
  ],
  "rule": "Agent runs can draft, read and explain; decision, send and pay endpoints reject agent actors.",
  "scope": "Decisions, assistant"
}
```

### INV-RESEND — Check before resending

```json
{
  "id": "INV-RESEND",
  "title": "Check before resending",
  "refs": [
    "REC-WORK",
    "REC-NOTIFICATION",
    "A-RECONCILE"
  ],
  "evidence": [
    "S-SCOPE",
    "S-BACKEND"
  ],
  "rule": "A send with an unknown outcome blocks any new send until reconciled.",
  "scope": "Deliveries, alerts"
}
```

### INV-AUDIT — History is append-only

```json
{
  "id": "INV-AUDIT",
  "title": "History is append-only",
  "refs": [
    "REC-AUDIT",
    "A-HISTORY",
    "A-DECIDE"
  ],
  "evidence": [
    "S-SCOPE",
    "S-BACKEND"
  ],
  "rule": "Every write adds an audit event; nothing edits or deletes one.",
  "scope": "All writes"
}
```

### INV-RESTRICTED — Payroll rows stay with HR

```json
{
  "id": "INV-RESTRICTED",
  "title": "Payroll rows stay with HR",
  "refs": [
    "REC-GRANT",
    "A-PAYROLL",
    "A-ASSISTANT"
  ],
  "evidence": [
    "S-SCOPE",
    "S-BACKEND"
  ],
  "rule": "Individual payroll rows are returned only to roles with payroll private read; others get totals.",
  "scope": "Payroll, BU totals"
}
```

### INV-SAMPLE — Sample data is labelled

```json
{
  "id": "INV-SAMPLE",
  "title": "Sample data is labelled",
  "refs": [
    "REC-CASE",
    "A-MYWORK"
  ],
  "evidence": [
    "S-SCOPE",
    "S-BACKEND"
  ],
  "rule": "Records from synthetic or demo cases carry sample=true in every payload.",
  "scope": "All payloads"
}
```

## Journeys

### JR-01 — Start work to verified (J-01)

```json
{
  "id": "JR-01",
  "title": "Start work to verified (J-01)",
  "refs": [
    "E-LINES",
    "E-WORK-START",
    "E-WORK-ITEM",
    "E-LINE-OPTIONS",
    "E-EVIDENCE-UPLOAD"
  ],
  "evidence": [
    "S-SCOPE",
    "S-SCREENS"
  ],
  "success": [
    "Open Start work",
    "Fill intake",
    "Line starts; follow it to verified"
  ],
  "failure": [
    "Missing field: 422 names it",
    "No permission: line not offered"
  ]
}
```

### JR-02 — Decide from an alert (J-02)

```json
{
  "id": "JR-02",
  "title": "Decide from an alert (J-02)",
  "refs": [
    "E-NOTIFICATIONS",
    "E-WORK-ITEM",
    "E-TASK-CLAIM",
    "E-TASK-DECIDE"
  ],
  "evidence": [
    "S-SCOPE",
    "S-SCREENS"
  ],
  "success": [
    "Open alert link",
    "Read the exact version",
    "Approve, return or reject"
  ],
  "failure": [
    "Version changed: 409, reload newer version",
    "Not eligible: read-only view names the role"
  ]
}
```

### JR-03 — Record an outside response (J-03)

```json
{
  "id": "JR-03",
  "title": "Record an outside response (J-03)",
  "refs": [
    "E-EVIDENCE-UPLOAD",
    "E-RESPONSE",
    "E-WORK-ITEM",
    "E-RFP-OUTCOME",
    "E-RFP-FOLLOWUP"
  ],
  "evidence": [
    "S-SCOPE",
    "S-SCREENS"
  ],
  "success": [
    "Upload proof",
    "Record who, what, when, attest"
  ],
  "failure": [
    "No proof: 422"
  ]
}
```

### JR-05 — Clear an exception (J-05, J-07)

```json
{
  "id": "JR-05",
  "title": "Clear an exception (J-05, J-07)",
  "refs": [
    "E-EXCEPTIONS",
    "E-WORK-ACTION",
    "E-SETUP-RULE-SAVE",
    "E-WORK-STEP"
  ],
  "evidence": [
    "S-SCOPE",
    "S-SCREENS"
  ],
  "success": [
    "See exception",
    "Reconcile or set the missing rule",
    "Resume"
  ],
  "failure": [
    "Outcome still unknown: stays held"
  ]
}
```

### JR-06 — Restricted payroll (J-06)

```json
{
  "id": "JR-06",
  "title": "Restricted payroll (J-06)",
  "refs": [
    "E-PAYROLL-MATCH"
  ],
  "evidence": [
    "S-SCOPE",
    "S-SCREENS"
  ],
  "success": [
    "HR reviews the match",
    "Totals published"
  ],
  "failure": [
    "Finance user: 403 on rows"
  ]
}
```

### JR-08 — Project journey (J-08)

```json
{
  "id": "JR-08",
  "title": "Project journey (J-08)",
  "refs": [
    "E-PROJECTS",
    "E-PROJECT",
    "E-PROJECT-TAB"
  ],
  "evidence": [
    "S-SCOPE",
    "S-SCREENS"
  ],
  "success": [
    "Open project",
    "See every line and what is next"
  ],
  "failure": [
    "No grant: 404"
  ]
}
```

### JR-10 — Assistant (J-10, J-11)

```json
{
  "id": "JR-10",
  "title": "Assistant (J-10, J-11)",
  "refs": [
    "E-CONVERSATION-NEW",
    "E-MESSAGE",
    "E-CONVERSATION"
  ],
  "evidence": [
    "S-SCOPE",
    "S-SCREENS"
  ],
  "success": [
    "Ask",
    "See steps and sources",
    "Start the drafted line"
  ],
  "failure": [
    "No access to a record: cannot answer, says why"
  ]
}
```

## Jobs

### JOB-ALERTS — Send alerts

```json
{
  "id": "JOB-ALERTS",
  "title": "Send alerts",
  "refs": [
    "REC-NOTIFICATION",
    "REC-ALERT-PREF",
    "INV-RESEND",
    "I-ALERTS",
    "T-ALERTS"
  ],
  "evidence": [
    "S-BACKEND"
  ],
  "trigger": "Outbox entry from a notification",
  "consumer": "work_outbox (alert adapter)",
  "retry_limit": 3,
  "recovery": "After the limit, park and show the send as uncertain; reconcile before any resend."
}
```

### JOB-ASSISTANT — Answer an assistant message

```json
{
  "id": "JOB-ASSISTANT",
  "title": "Answer an assistant message",
  "refs": [
    "REC-CONVERSATION",
    "REC-AGENTRUN",
    "INV-AGENT",
    "I-AGENT",
    "T-ASSISTANT"
  ],
  "evidence": [
    "S-BACKEND"
  ],
  "trigger": "Message stored by E-MESSAGE",
  "consumer": "agents coordinator worker",
  "retry_limit": 2,
  "recovery": "Mark the run stopped with a reason; the conversation shows cannot answer; the person may ask again."
}
```

## Runbooks

### O-STALE — People report "this version changed" repeatedly

```json
{
  "id": "O-STALE",
  "title": "People report \"this version changed\" repeatedly",
  "refs": [
    "E-TASK-DECIDE",
    "REC-TASK"
  ],
  "evidence": [
    "S-BACKEND"
  ],
  "trigger": "Repeated 409 responses on one task",
  "steps": [
    "Read the work item history for revisions",
    "Check whether an agent keeps redrafting",
    "Never bypass the revision check"
  ],
  "recovery": "Stop the redrafting cause; the person reloads and decides the current version.",
  "owner": "developer"
}
```

### O-UNCERTAIN — A send outcome is unknown

```json
{
  "id": "O-UNCERTAIN",
  "title": "A send outcome is unknown",
  "refs": [
    "E-WORK-ACTION",
    "REC-WORK"
  ],
  "evidence": [
    "S-BACKEND"
  ],
  "trigger": "Work shows effect uncertain",
  "steps": [
    "Check the provider or recipient for receipt",
    "Record delivered, not delivered or still unknown with evidence",
    "Resend only after not delivered is recorded"
  ],
  "recovery": "Reconcile through E-WORK-ACTION.",
  "owner": "operator"
}
```

## Integrations

### I-ALERTS — WhatsApp and email alerts

```json
{
  "id": "I-ALERTS",
  "title": "WhatsApp and email alerts",
  "refs": [
    "D-NOTIFY-MODEL",
    "D-ALERT-PROVIDERS",
    "T-ALERTS",
    "JOB-ALERTS"
  ],
  "evidence": [
    "S-SCOPE",
    "S-BACKEND"
  ],
  "provider": "Not chosen (mock adapter)",
  "selection": "unresolved",
  "purpose": "Tell people what is waiting for them (I-03).",
  "data": "Agent name, one line, work reference, app link; no amounts or client details.",
  "secret_boundary": "Provider credentials server-only; never in the frontend.",
  "failure_recovery": "Outbox retries up to 3 times; an unknown send outcome is reconciled before any resend.",
  "operations": [
    {
      "name": "queue_alert",
      "relationship": "queued_work",
      "contract": "From T-ALERTS on, decision and state changes (E-TASK-DECIDE, E-WORK-ACTION) write Notification rows and an outbox entry; E-NOTIFICATIONS lists them; JOB-ALERTS sends per preference.",
      "authentication": "Internal; no external call at queue time.",
      "evidence": [
        "S-BACKEND"
      ]
    }
  ]
}
```

### I-AGENT — Agent language model provider

```json
{
  "id": "I-AGENT",
  "title": "Agent language model provider",
  "refs": [
    "D-AGENT-PROVIDER",
    "T-ASSISTANT",
    "JOB-ASSISTANT"
  ],
  "evidence": [
    "S-BACKEND",
    "S-SCOPE"
  ],
  "provider": "Not chosen (synthetic provider)",
  "selection": "unresolved",
  "purpose": "Agent steps and assistant answers (S-10).",
  "data": "Only records the requesting person may read; payroll private rows never leave HR scope.",
  "secret_boundary": "Provider key server-only.",
  "failure_recovery": "Agent run marked stopped with a reason; the person sees \"cannot answer\"; no record changes.",
  "operations": [
    {
      "name": "run_assistant",
      "relationship": "queued_work",
      "contract": "E-MESSAGE stores the message and queues JOB-ASSISTANT; the worker calls the provider and stores the answer with sources.",
      "authentication": "Internal queue; provider call authenticated server-side when chosen.",
      "evidence": [
        "S-BACKEND"
      ]
    }
  ]
}
```

### I-CLIENT-MESSAGES — Messages to clients (RFP follow-ups, payment reminders, report sends)

```json
{
  "id": "I-CLIENT-MESSAGES",
  "title": "Messages to clients (RFP follow-ups, payment reminders, report sends)",
  "refs": [
    "D-ALERT-PROVIDERS",
    "D-RFP-OUTCOME",
    "D-LINE-WORKSPACE",
    "T-RESPONSE",
    "T-WORKSPACE"
  ],
  "evidence": [
    "S-SCOPE",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "provider": "Not chosen (existing delivery outbox with a mock adapter)",
  "selection": "unresolved",
  "purpose": "Send what a person approved or chose to send to a client contact (e.g. the RFP follow-up on SCR-16 rfp-unknown, the payment reminder on SCR-32).",
  "data": "Only the exact version the person sent; recipient as recorded by the backend.",
  "secret_boundary": "Provider credentials server-only; never in the frontend.",
  "failure_recovery": "An unknown send outcome makes the work effect_uncertain; it is reconciled (E-WORK-ACTION) before any resend (INV-RESEND).",
  "operations": [
    {
      "name": "queue_client_message",
      "relationship": "queued_work",
      "contract": "E-RFP-FOLLOWUP and sending steps on E-WORK-STEP write an outbox entry for the exact version; the outbox worker sends it and records the receipt or an uncertain effect.",
      "authentication": "Internal; provider call authenticated server-side when chosen.",
      "evidence": [
        "S-BACKEND",
        "S-DECISIONS-V6"
      ]
    }
  ]
}
```

## Endpoints

### E-ME — Who I am and what I may use

```json
{
  "id": "E-ME",
  "title": "Who I am and what I may use",
  "refs": [
    "R-SESSION",
    "REC-GRANT",
    "INV-ACCESS",
    "D-AUTH",
    "D-API-STYLE",
    "T-FOUNDATION",
    "A-ME",
    "D-START-INTAKE",
    "D-ASSISTANT-VIEW",
    "A-ASSISTANT-THREADS"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V5",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "GET",
  "path": "/api/v1/me",
  "trigger": "App load",
  "security": [
    "Session"
  ],
  "permission": "Signed in.",
  "parameters": [],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Who I am and what I may use",
      "schema": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "minLength": 1
          },
          "roles": {
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1
            }
          },
          "destinations": {
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1,
              "enum": [
                "my_work",
                "projects",
                "overview",
                "assistant",
                "setup"
              ]
            }
          },
          "startable_lines": {
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1
            },
            "description": "PROPOSAL (D-START-INTAKE): line keys, the same as E-LINES items[].key, never display titles. Start work shows when the list is not empty."
          },
          "csrf_token": {
            "type": "string",
            "minLength": 1
          },
          "assistant_agents": {
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1,
              "enum": [
                "tola",
                "chidi",
                "zainab"
              ]
            },
            "description": "PROPOSAL (D-ASSISTANT-VIEW): the agents this person may talk to, as the backend allows"
          }
        },
        "required": [
          "name",
          "roles",
          "destinations",
          "startable_lines",
          "csrf_token"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.me.read",
  "service": "identity.services",
  "local_work": "Resolve the record, check grants and authority, call identity.services.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-WORK-LIST — My work queue

```json
{
  "id": "E-WORK-LIST",
  "title": "My work queue",
  "refs": [
    "R-MYWORK",
    "REC-WORK",
    "REC-TASK",
    "INV-ACCESS",
    "INV-SAMPLE",
    "D-PAGING",
    "D-UPDATES",
    "T-MYWORK",
    "A-MYWORK",
    "D-WORKLIST-FILTERS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V3"
  ],
  "method": "GET",
  "path": "/api/v1/work",
  "trigger": "My work page, queue tab, search, filter",
  "security": [
    "Session"
  ],
  "permission": "Signed in; rows filtered by grants.",
  "parameters": [
    {
      "name": "queue",
      "in": "query",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "needs_me",
          "waiting_on_others",
          "done",
          "unassigned"
        ]
      }
    },
    {
      "name": "q",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "line",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1,
        "description": "Line key (filters.lines[].key or a row's line_key), never the display title"
      }
    },
    {
      "name": "project",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1,
        "description": "Project case_id, from E-PROJECTS"
      }
    },
    {
      "name": "waiting_on",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "me",
          "someone_else",
          "agent",
          "outside_party",
          "no_owner"
        ],
        "description": "PROPOSAL (D-WORKLIST-FILTERS)"
      }
    },
    {
      "name": "state",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "cursor",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "limit",
      "in": "query",
      "required": false,
      "schema": {
        "type": "integer",
        "enum": [
          10,
          20,
          50
        ],
        "description": "Rows per page chosen by the person; default 20"
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "My work queue",
      "schema": {
        "type": "object",
        "properties": {
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "id": {
                  "type": "string",
                  "minLength": 1
                },
                "title": {
                  "type": "string",
                  "minLength": 1
                },
                "line": {
                  "type": "string",
                  "minLength": 1
                },
                "reference": {
                  "type": "string",
                  "minLength": 1
                },
                "kind": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "decide",
                    "do",
                    "fix",
                    "started"
                  ]
                },
                "state": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "ready",
                    "processing",
                    "waiting",
                    "owner_needed",
                    "setup_needed",
                    "action_needed",
                    "effect_uncertain",
                    "awaiting_reconciliation",
                    "verified",
                    "cancelled",
                    "followup_needed"
                  ]
                },
                "station": {
                  "type": "object",
                  "properties": {
                    "index": {
                      "type": "integer",
                      "minimum": 1
                    },
                    "count": {
                      "type": "integer",
                      "minimum": 1
                    },
                    "name": {
                      "type": "string",
                      "minLength": 1
                    }
                  },
                  "required": [
                    "index",
                    "count",
                    "name"
                  ],
                  "additionalProperties": false
                },
                "waiting_on": {
                  "type": "string",
                  "minLength": 1
                },
                "age_seconds": {
                  "type": "integer",
                  "minimum": 0
                },
                "sample": {
                  "type": "boolean"
                },
                "line_key": {
                  "type": "string",
                  "minLength": 1
                },
                "agent": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "tola",
                    "chidi",
                    "zainab"
                  ]
                }
              },
              "required": [
                "id",
                "title",
                "line",
                "reference",
                "kind",
                "state",
                "station",
                "waiting_on",
                "age_seconds",
                "sample"
              ],
              "additionalProperties": false
            }
          },
          "next_cursor": {
            "type": "string"
          },
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          },
          "counts": {
            "type": "object",
            "properties": {
              "needs_me": {
                "type": "integer",
                "minimum": 0
              },
              "waiting_on_others": {
                "type": "integer",
                "minimum": 0
              },
              "done": {
                "type": "integer",
                "minimum": 0
              },
              "unassigned": {
                "type": "integer",
                "minimum": 0
              }
            },
            "required": [
              "needs_me",
              "waiting_on_others",
              "done"
            ],
            "additionalProperties": false
          },
          "filters": {
            "type": "object",
            "properties": {
              "lines": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "key": {
                      "type": "string",
                      "minLength": 1
                    },
                    "title": {
                      "type": "string",
                      "minLength": 1
                    }
                  },
                  "required": [
                    "key",
                    "title"
                  ],
                  "additionalProperties": false
                }
              }
            },
            "required": [
              "lines"
            ],
            "additionalProperties": false
          }
        },
        "required": [
          "items",
          "as_of"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.work.list",
  "service": "workflows.factory.snapshot",
  "local_work": "Resolve the record, check grants and authority, call workflows.factory.snapshot.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-WORK-ITEM — One work item

```json
{
  "id": "E-WORK-ITEM",
  "title": "One work item",
  "refs": [
    "R-WORKITEM",
    "REC-WORK",
    "REC-TASK",
    "REC-AGENTRUN",
    "REC-DOCUMENT",
    "INV-ACCESS",
    "INV-FACTS",
    "INV-UNKNOWN",
    "INV-AGENT",
    "INV-SAMPLE",
    "D-UPDATES",
    "T-WORKITEM",
    "A-WORKITEM",
    "D-WORKITEM-DETAIL",
    "D-TASK-DECISION-VIEW",
    "A-NOT-YOURS",
    "D-RESPONSE-VIEW",
    "D-WORK-ACTIONS-VIEW",
    "D-RFP-OUTCOME",
    "A-RESPONSE",
    "A-RECONCILE",
    "D-LINE-WORKSPACE",
    "D-RFP-INTAKE",
    "A-WORKSPACE"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V3",
    "S-DECISIONS-V5",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "GET",
  "path": "/api/v1/work/{work_id}",
  "trigger": "Open a row or an alert link",
  "security": [
    "Session"
  ],
  "permission": "case.read plus the line's read permission.",
  "parameters": [
    {
      "name": "work_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "One work item",
      "schema": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string",
            "minLength": 1
          },
          "title": {
            "type": "string",
            "minLength": 1
          },
          "line": {
            "type": "string",
            "minLength": 1
          },
          "reference": {
            "type": "string",
            "minLength": 1
          },
          "state": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "ready",
              "processing",
              "waiting",
              "owner_needed",
              "setup_needed",
              "action_needed",
              "effect_uncertain",
              "awaiting_reconciliation",
              "verified",
              "cancelled",
              "followup_needed"
            ]
          },
          "revision": {
            "type": "integer",
            "minimum": 1
          },
          "stations": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": {
                  "type": "string",
                  "minLength": 1
                },
                "status": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "done",
                    "current_person",
                    "current_agent",
                    "waiting",
                    "stopped",
                    "not_started",
                    "verified"
                  ]
                },
                "started_at": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date-time"
                },
                "finished_at": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date-time"
                },
                "held_by": {
                  "type": "object",
                  "properties": {
                    "kind": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "person",
                        "role",
                        "agent",
                        "outside_party",
                        "factory"
                      ]
                    },
                    "name": {
                      "type": "string",
                      "minLength": 1,
                      "description": "Person, role, agent or outside party name as recorded"
                    },
                    "is_you": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "kind",
                    "name",
                    "is_you"
                  ],
                  "additionalProperties": false
                }
              },
              "required": [
                "name",
                "status"
              ],
              "additionalProperties": false
            }
          },
          "facts": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "drafted",
                    "reviewed",
                    "approved",
                    "sent",
                    "receipt_recorded",
                    "verified"
                  ]
                },
                "status": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "earned",
                    "current",
                    "not_yet",
                    "unknown"
                  ]
                },
                "at": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date-time"
                }
              },
              "required": [
                "name",
                "status"
              ],
              "additionalProperties": false
            }
          },
          "tasks": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "id": {
                  "type": "string",
                  "minLength": 1
                },
                "kind": {
                  "type": "string",
                  "minLength": 1,
                  "description": "Task kind as named by the backend. A task with a response block is a recorded response (open the response form); one with a decision block is a decision."
                },
                "title": {
                  "type": "string",
                  "minLength": 1
                },
                "required_role": {
                  "type": "string",
                  "minLength": 1
                },
                "you_can_act": {
                  "type": "boolean"
                },
                "revision": {
                  "type": "integer",
                  "minimum": 1
                },
                "decision": {
                  "type": "object",
                  "properties": {
                    "version": {
                      "type": "object",
                      "properties": {
                        "label": {
                          "type": "string",
                          "minLength": 1,
                          "description": "As shown on the board, e.g. \"Invoice v2\""
                        },
                        "number": {
                          "type": "integer",
                          "minimum": 1
                        },
                        "document_id": {
                          "type": "string",
                          "minLength": 1
                        },
                        "drafted_at": {
                          "type": "string",
                          "minLength": 1,
                          "format": "date-time"
                        }
                      },
                      "required": [
                        "label",
                        "number"
                      ],
                      "additionalProperties": false
                    },
                    "amount": {
                      "type": "object",
                      "properties": {
                        "amount": {
                          "type": "string",
                          "minLength": 1,
                          "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                          "description": "Decimal string; absent when unknown"
                        },
                        "currency": {
                          "type": "string",
                          "minLength": 1,
                          "pattern": "^[A-Z]{3}$"
                        },
                        "unknown": {
                          "type": "boolean"
                        }
                      },
                      "required": [
                        "currency",
                        "unknown"
                      ],
                      "additionalProperties": false,
                      "description": "Amount of the exact version being decided; absent when the decision carries no amount. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                    },
                    "basis": {
                      "type": "string",
                      "minLength": 1,
                      "description": "Plain-language basis composed by the backend from contract terms, e.g. \"Contract stage 2 of 4 · terms v1\""
                    },
                    "recipient": {
                      "type": "string",
                      "minLength": 1,
                      "description": "Who the output goes to when sent, e.g. a billing email; absent when nothing is sent"
                    },
                    "changes": {
                      "type": "object",
                      "properties": {
                        "previous_label": {
                          "type": "string",
                          "minLength": 1
                        },
                        "items": {
                          "type": "array",
                          "items": {
                            "type": "string",
                            "minLength": 1
                          }
                        }
                      },
                      "required": [
                        "previous_label",
                        "items"
                      ],
                      "additionalProperties": false
                    },
                    "prepared_by": {
                      "type": "object",
                      "properties": {
                        "name": {
                          "type": "string",
                          "minLength": 1
                        },
                        "role": {
                          "type": "string",
                          "minLength": 1
                        },
                        "is_you": {
                          "type": "boolean"
                        },
                        "with_agent": {
                          "type": "string",
                          "minLength": 1,
                          "enum": [
                            "tola",
                            "chidi",
                            "zainab"
                          ]
                        }
                      },
                      "required": [
                        "name",
                        "is_you"
                      ],
                      "additionalProperties": false
                    },
                    "chain": {
                      "type": "object",
                      "properties": {
                        "steps": {
                          "type": "array",
                          "items": {
                            "type": "object",
                            "properties": {
                              "position": {
                                "type": "integer",
                                "minimum": 1
                              },
                              "role": {
                                "type": "string",
                                "minLength": 1
                              },
                              "person": {
                                "type": "string",
                                "minLength": 1,
                                "description": "Absent until a person is assigned"
                              },
                              "status": {
                                "type": "string",
                                "minLength": 1,
                                "enum": [
                                  "approved",
                                  "returned",
                                  "rejected",
                                  "withdrawn",
                                  "current",
                                  "not_yet"
                                ]
                              },
                              "decided_at": {
                                "type": "string",
                                "minLength": 1,
                                "format": "date-time"
                              },
                              "is_you": {
                                "type": "boolean"
                              }
                            },
                            "required": [
                              "position",
                              "role",
                              "status",
                              "is_you"
                            ],
                            "additionalProperties": false
                          }
                        },
                        "your_step": {
                          "type": "integer",
                          "minimum": 1
                        },
                        "step_count": {
                          "type": "integer",
                          "minimum": 1
                        }
                      },
                      "required": [
                        "steps",
                        "step_count"
                      ],
                      "additionalProperties": false
                    }
                  },
                  "required": [
                    "version",
                    "chain"
                  ],
                  "additionalProperties": false,
                  "description": "PROPOSAL (D-TASK-DECISION-VIEW). Present on decision tasks. Every value comes from backend records and the line's configured approval order; the frontend shows only what is returned. your_step is absent when the person has no step."
                },
                "cannot_act_reason": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "not_your_role",
                    "prepared_by_you",
                    "already_decided",
                    "not_your_turn"
                  ],
                  "description": "Present only when you_can_act is false"
                },
                "asked": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "name": {
                        "type": "string",
                        "minLength": 1
                      },
                      "role": {
                        "type": "string",
                        "minLength": 1
                      },
                      "alerted_at": {
                        "type": "string",
                        "minLength": 1,
                        "format": "date-time"
                      },
                      "channels": {
                        "type": "array",
                        "items": {
                          "type": "string",
                          "minLength": 1,
                          "enum": [
                            "whatsapp",
                            "email"
                          ]
                        }
                      }
                    },
                    "required": [
                      "name",
                      "role"
                    ],
                    "additionalProperties": false
                  },
                  "description": "Who was asked to act on this task (shown when you cannot act); empty when nobody is assigned yet."
                },
                "response": {
                  "type": "object",
                  "properties": {
                    "variant": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "client_response",
                        "sow_signature",
                        "team_input",
                        "go_live_acceptance",
                        "support_handover"
                      ],
                      "description": "Which SCR-16 form to show"
                    },
                    "responders": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "id": {
                            "type": "string",
                            "minLength": 1
                          },
                          "name": {
                            "type": "string",
                            "minLength": 1
                          },
                          "role": {
                            "type": "string",
                            "minLength": 1
                          },
                          "organisation": {
                            "type": "string",
                            "minLength": 1
                          }
                        },
                        "required": [
                          "id",
                          "name"
                        ],
                        "additionalProperties": false
                      }
                    },
                    "actions": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "value": {
                            "type": "string",
                            "minLength": 1,
                            "enum": [
                              "approved",
                              "changes_requested",
                              "signed",
                              "rejected",
                              "estimate",
                              "input"
                            ]
                          },
                          "label": {
                            "type": "string",
                            "minLength": 1
                          }
                        },
                        "required": [
                          "value"
                        ],
                        "additionalProperties": false
                      }
                    },
                    "versions": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "id": {
                            "type": "string",
                            "minLength": 1
                          },
                          "label": {
                            "type": "string",
                            "minLength": 1
                          },
                          "note": {
                            "type": "string",
                            "minLength": 1,
                            "description": "e.g. \"the version sent for UAT\""
                          },
                          "sent_at": {
                            "type": "string",
                            "minLength": 1,
                            "format": "date-time"
                          }
                        },
                        "required": [
                          "id",
                          "label"
                        ],
                        "additionalProperties": false
                      }
                    },
                    "teams": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "key": {
                            "type": "string",
                            "minLength": 1
                          },
                          "name": {
                            "type": "string",
                            "minLength": 1
                          },
                          "given": {
                            "type": "boolean"
                          },
                          "estimate_needed": {
                            "type": "boolean"
                          }
                        },
                        "required": [
                          "key",
                          "name",
                          "given"
                        ],
                        "additionalProperties": false
                      }
                    },
                    "blocking": {
                      "type": "string",
                      "minLength": 1,
                      "description": "Plain sentence on who holds review, e.g. \"Security and Product haven't given input yet.\""
                    },
                    "evidence_kind": {
                      "type": "string",
                      "minLength": 1
                    },
                    "claim_required": {
                      "type": "boolean"
                    },
                    "intro": {
                      "type": "string",
                      "minLength": 1,
                      "description": "Sentence above the form as composed by the backend, e.g. \"Lagoon Health's client contact doesn't log in… The release waits for this.\""
                    },
                    "proof_hint": {
                      "type": "string",
                      "minLength": 1,
                      "description": "Hint under the proof field, e.g. \"Signed PDF, e-signature record, or the client's email saved as PDF\""
                    },
                    "agent_note": {
                      "type": "object",
                      "properties": {
                        "agent": {
                          "type": "string",
                          "minLength": 1,
                          "enum": [
                            "tola",
                            "chidi",
                            "zainab"
                          ]
                        },
                        "lines": {
                          "type": "array",
                          "items": {
                            "type": "string",
                            "minLength": 1
                          }
                        }
                      },
                      "required": [
                        "agent",
                        "lines"
                      ],
                      "additionalProperties": false
                    },
                    "channels": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "value": {
                            "type": "string",
                            "minLength": 1
                          },
                          "label": {
                            "type": "string",
                            "minLength": 1
                          }
                        },
                        "required": [
                          "value",
                          "label"
                        ],
                        "additionalProperties": false
                      },
                      "description": "How the response may have been received (e.g. email, letter, in person), as the backend lists them; sent back as received_via"
                    },
                    "context": {
                      "type": "object",
                      "properties": {
                        "project": {
                          "type": "object",
                          "properties": {
                            "case_id": {
                              "type": "string",
                              "minLength": 1
                            },
                            "title": {
                              "type": "string",
                              "minLength": 1
                            }
                          },
                          "required": [
                            "case_id",
                            "title"
                          ],
                          "additionalProperties": false
                        },
                        "document": {
                          "type": "object",
                          "properties": {
                            "reference": {
                              "type": "string",
                              "minLength": 1
                            },
                            "label": {
                              "type": "string",
                              "minLength": 1
                            },
                            "document_id": {
                              "type": "string",
                              "minLength": 1
                            }
                          },
                          "required": [
                            "reference"
                          ],
                          "additionalProperties": false
                        }
                      },
                      "required": [],
                      "additionalProperties": false
                    },
                    "next": {
                      "type": "array",
                      "items": {
                        "type": "string",
                        "minLength": 1,
                        "description": "\"What happens next\" lines, e.g. \"the SOW's 4 stages become the project's milestones\""
                      }
                    },
                    "recorded": {
                      "type": "object",
                      "properties": {
                        "by": {
                          "type": "object",
                          "properties": {
                            "name": {
                              "type": "string",
                              "minLength": 1
                            },
                            "role": {
                              "type": "string",
                              "minLength": 1
                            },
                            "is_you": {
                              "type": "boolean"
                            }
                          },
                          "required": [
                            "name"
                          ],
                          "additionalProperties": false
                        },
                        "at": {
                          "type": "string",
                          "minLength": 1,
                          "format": "date-time"
                        },
                        "responded_at": {
                          "type": "string",
                          "minLength": 1,
                          "format": "date-time"
                        },
                        "received_via": {
                          "type": "string",
                          "minLength": 1,
                          "description": "One of response.channels[].value"
                        },
                        "proof_count": {
                          "type": "integer",
                          "minimum": 0
                        },
                        "summary": {
                          "type": "string",
                          "minLength": 1
                        }
                      },
                      "required": [
                        "by",
                        "at"
                      ],
                      "additionalProperties": false,
                      "description": "Present once the response is recorded (success board): who recorded it, when, how it was received and how many proof files"
                    }
                  },
                  "required": [
                    "actions",
                    "responders"
                  ],
                  "additionalProperties": false,
                  "description": "PROPOSAL (D-RESPONSE-VIEW): present on tasks a person records for someone who does not log in. Which actions a task accepts and who may have responded are backend rules; the frontend offers only what is listed. claim_required true: call E-TASK-CLAIM before E-RESPONSE."
                }
              },
              "required": [
                "id",
                "kind",
                "title",
                "required_role",
                "you_can_act",
                "revision"
              ],
              "additionalProperties": false
            }
          },
          "agent": {
            "type": "object",
            "properties": {
              "name": {
                "type": "string",
                "minLength": 1
              },
              "status": {
                "type": "string",
                "minLength": 1,
                "enum": [
                  "working",
                  "done",
                  "waiting",
                  "stopped",
                  "none"
                ]
              },
              "steps": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "text": {
                      "type": "string",
                      "minLength": 1
                    },
                    "status": {
                      "type": "string",
                      "minLength": 1
                    },
                    "source": {
                      "type": "string"
                    },
                    "at": {
                      "type": "string",
                      "minLength": 1,
                      "format": "date-time"
                    }
                  },
                  "required": [
                    "text",
                    "status"
                  ],
                  "additionalProperties": false
                }
              },
              "started_at": {
                "type": "string",
                "minLength": 1,
                "format": "date-time"
              }
            },
            "required": [
              "status"
            ],
            "additionalProperties": false
          },
          "next_step": {
            "type": "string",
            "minLength": 1
          },
          "sample": {
            "type": "boolean"
          },
          "amount": {
            "type": "object",
            "properties": {
              "amount": {
                "type": "string",
                "minLength": 1,
                "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                "description": "Decimal string; absent when unknown"
              },
              "currency": {
                "type": "string",
                "minLength": 1,
                "pattern": "^[A-Z]{3}$"
              },
              "unknown": {
                "type": "boolean"
              }
            },
            "required": [
              "currency",
              "unknown"
            ],
            "additionalProperties": false,
            "description": "Amount of the work item (e.g. the invoice); absent when the line carries no amount. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
          },
          "started_by": {
            "type": "object",
            "properties": {
              "name": {
                "type": "string",
                "minLength": 1
              },
              "role": {
                "type": "string",
                "minLength": 1
              },
              "is_you": {
                "type": "boolean"
              }
            },
            "required": [
              "name",
              "is_you"
            ],
            "additionalProperties": false
          },
          "started_at": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          },
          "case_id": {
            "type": "string",
            "minLength": 1,
            "description": "Case the work belongs to; the path for E-EVIDENCE-UPLOAD"
          },
          "case_revision": {
            "type": "integer",
            "minimum": 1
          },
          "allowed_actions": {
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1,
              "enum": [
                "resume",
                "cancel",
                "reconcile"
              ]
            },
            "description": "PROPOSAL (D-WORK-ACTIONS-VIEW): the E-WORK-ACTION actions this person may take now, decided by the backend. Absent or empty: offer none."
          },
          "reconcile": {
            "type": "object",
            "properties": {
              "what": {
                "type": "string",
                "minLength": 1,
                "description": "What was sent, e.g. \"Invoice INV-0412 v2 to the billing contact\""
              },
              "sent_at": {
                "type": "string",
                "minLength": 1,
                "format": "date-time"
              },
              "checks": {
                "type": "object",
                "properties": {
                  "count": {
                    "type": "integer",
                    "minimum": 0
                  },
                  "first_at": {
                    "type": "string",
                    "minLength": 1,
                    "format": "date-time"
                  },
                  "last_at": {
                    "type": "string",
                    "minLength": 1,
                    "format": "date-time"
                  },
                  "agent": {
                    "type": "string",
                    "minLength": 1,
                    "enum": [
                      "tola",
                      "chidi",
                      "zainab"
                    ]
                  }
                },
                "required": [
                  "count"
                ],
                "additionalProperties": false
              },
              "outcomes": {
                "type": "array",
                "items": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "delivered",
                    "not_delivered",
                    "unknown"
                  ]
                }
              },
              "evidence_kind": {
                "type": "string",
                "minLength": 1
              },
              "resend": {
                "type": "string",
                "minLength": 1,
                "description": "What a not-delivered answer allows, as the backend states it, e.g. \"one resend of the same version\""
              },
              "unknown_note": {
                "type": "string",
                "minLength": 1,
                "description": "What \"I can't tell yet\" does, as the backend states it, e.g. \"Keep it held and remind me tomorrow\""
              },
              "resend_note": {
                "type": "string",
                "minLength": 1,
                "description": "What a resend reuses, e.g. \"A resend reuses the same invoice number\""
              }
            },
            "required": [
              "outcomes"
            ],
            "additionalProperties": false,
            "description": "PROPOSAL (D-WORK-ACTIONS-VIEW): present when the state is awaiting_reconciliation or effect_uncertain."
          },
          "rfp_outcome": {
            "type": "object",
            "properties": {
              "submission": {
                "type": "object",
                "properties": {
                  "id": {
                    "type": "string",
                    "minLength": 1
                  },
                  "label": {
                    "type": "string",
                    "minLength": 1
                  },
                  "sent_at": {
                    "type": "string",
                    "minLength": 1,
                    "format": "date-time"
                  },
                  "delivery": {
                    "type": "string",
                    "minLength": 1
                  }
                },
                "required": [
                  "id",
                  "label"
                ],
                "additionalProperties": false
              },
              "results": {
                "type": "array",
                "items": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "won",
                    "lost",
                    "pending",
                    "unknown"
                  ]
                }
              },
              "reasons": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "value": {
                      "type": "string",
                      "minLength": 1
                    },
                    "label": {
                      "type": "string",
                      "minLength": 1
                    }
                  },
                  "required": [
                    "value",
                    "label"
                  ],
                  "additionalProperties": false
                }
              },
              "record_as": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "value": {
                      "type": "string",
                      "minLength": 1
                    },
                    "label": {
                      "type": "string",
                      "minLength": 1
                    }
                  },
                  "required": [
                    "value",
                    "label"
                  ],
                  "additionalProperties": false
                }
              },
              "evidence_kind": {
                "type": "string",
                "minLength": 1
              },
              "recorded": {
                "type": "object",
                "properties": {
                  "result": {
                    "type": "string",
                    "minLength": 1,
                    "enum": [
                      "won",
                      "lost",
                      "pending",
                      "unknown"
                    ]
                  },
                  "at": {
                    "type": "string",
                    "minLength": 1,
                    "format": "date-time"
                  },
                  "by": {
                    "type": "string",
                    "minLength": 1
                  },
                  "rows": {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "properties": {
                        "label": {
                          "type": "string",
                          "minLength": 1
                        },
                        "value": {
                          "type": "string",
                          "minLength": 1
                        },
                        "at": {
                          "type": "string",
                          "minLength": 1,
                          "format": "date-time"
                        }
                      },
                      "required": [
                        "label",
                        "value"
                      ],
                      "additionalProperties": false
                    }
                  },
                  "reminder": {
                    "type": "object",
                    "properties": {
                      "holder": {
                        "type": "object",
                        "properties": {
                          "name": {
                            "type": "string",
                            "minLength": 1
                          },
                          "role": {
                            "type": "string",
                            "minLength": 1
                          },
                          "is_you": {
                            "type": "boolean"
                          }
                        },
                        "required": [
                          "name"
                        ],
                        "additionalProperties": false
                      },
                      "at": {
                        "type": "string",
                        "minLength": 1,
                        "format": "date-time"
                      }
                    },
                    "required": [
                      "holder",
                      "at"
                    ],
                    "additionalProperties": false
                  },
                  "lessons": {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "properties": {
                        "category": {
                          "type": "object",
                          "properties": {
                            "value": {
                              "type": "string",
                              "minLength": 1
                            },
                            "label": {
                              "type": "string",
                              "minLength": 1
                            }
                          },
                          "required": [
                            "value",
                            "label"
                          ],
                          "additionalProperties": false
                        },
                        "text": {
                          "type": "string",
                          "minLength": 1
                        }
                      },
                      "required": [
                        "text"
                      ],
                      "additionalProperties": false
                    }
                  },
                  "lessons_by": {
                    "type": "object",
                    "properties": {
                      "name": {
                        "type": "string",
                        "minLength": 1
                      },
                      "role": {
                        "type": "string",
                        "minLength": 1
                      },
                      "is_you": {
                        "type": "boolean"
                      }
                    },
                    "required": [
                      "name"
                    ],
                    "additionalProperties": false
                  },
                  "debrief": {
                    "type": "object",
                    "properties": {
                      "label": {
                        "type": "string",
                        "minLength": 1
                      },
                      "reference": {
                        "type": "string",
                        "minLength": 1
                      },
                      "work_id": {
                        "type": "string",
                        "minLength": 1
                      },
                      "document_id": {
                        "type": "string",
                        "minLength": 1
                      },
                      "case_id": {
                        "type": "string",
                        "minLength": 1
                      },
                      "evidence_id": {
                        "type": "string",
                        "minLength": 1
                      }
                    },
                    "required": [],
                    "additionalProperties": false
                  },
                  "archive_reference": {
                    "type": "string",
                    "minLength": 1,
                    "description": "e.g. ARC-0117"
                  },
                  "engagement": {
                    "type": "object",
                    "properties": {
                      "reference": {
                        "type": "string",
                        "minLength": 1
                      },
                      "work_id": {
                        "type": "string",
                        "minLength": 1
                      }
                    },
                    "required": [
                      "reference"
                    ],
                    "additionalProperties": false
                  },
                  "next": {
                    "type": "array",
                    "items": {
                      "type": "string",
                      "minLength": 1
                    }
                  }
                },
                "required": [
                  "result"
                ],
                "additionalProperties": false
              },
              "lesson_categories": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "value": {
                      "type": "string",
                      "minLength": 1
                    },
                    "label": {
                      "type": "string",
                      "minLength": 1
                    }
                  },
                  "required": [
                    "value",
                    "label"
                  ],
                  "additionalProperties": false
                }
              },
              "followup": {
                "type": "object",
                "properties": {
                  "to": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Recipient address exactly as the backend returns it"
                  },
                  "body": {
                    "type": "string",
                    "minLength": 1
                  },
                  "version": {
                    "type": "integer",
                    "minimum": 1
                  },
                  "agent": {
                    "type": "string",
                    "minLength": 1,
                    "enum": [
                      "tola",
                      "chidi",
                      "zainab"
                    ]
                  },
                  "checks": {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "properties": {
                        "text": {
                          "type": "string",
                          "minLength": 1
                        },
                        "source": {
                          "type": "string",
                          "minLength": 1
                        },
                        "status": {
                          "type": "string",
                          "minLength": 1,
                          "enum": [
                            "done",
                            "now",
                            "next"
                          ]
                        }
                      },
                      "required": [
                        "text",
                        "status"
                      ],
                      "additionalProperties": false
                    }
                  },
                  "status": {
                    "type": "string",
                    "minLength": 1,
                    "enum": [
                      "drafted",
                      "sending",
                      "sent",
                      "effect_uncertain"
                    ]
                  },
                  "sent_at": {
                    "type": "string",
                    "minLength": 1,
                    "format": "date-time"
                  },
                  "note": {
                    "type": "string",
                    "minLength": 1,
                    "description": "e.g. \"It goes only if you send it\""
                  },
                  "can_send": {
                    "type": "boolean"
                  },
                  "can_edit": {
                    "type": "boolean"
                  }
                },
                "required": [
                  "to",
                  "body",
                  "version",
                  "status"
                ],
                "additionalProperties": false,
                "description": "PROPOSAL (D-RFP-OUTCOME r2): a follow-up drafted by the agent. It is sent only by a person through E-RFP-FOLLOWUP; an uncertain send is reconciled before any resend (INV-RESEND)."
              }
            },
            "required": [
              "submission",
              "results",
              "record_as"
            ],
            "additionalProperties": false,
            "description": "PROPOSAL (D-RFP-OUTCOME): present on an RFP when the backend lets this person record its outcome. results, reasons and record_as come from the backend."
          },
          "rfp": {
            "type": "object",
            "properties": {
              "reference": {
                "type": "string",
                "minLength": 1
              },
              "title": {
                "type": "string",
                "minLength": 1
              },
              "client": {
                "type": "string",
                "minLength": 1
              },
              "status": {
                "type": "object",
                "properties": {
                  "kind": {
                    "type": "string",
                    "minLength": 1,
                    "enum": [
                      "deadline",
                      "submitted",
                      "won",
                      "lost",
                      "pending",
                      "unknown"
                    ]
                  },
                  "label": {
                    "type": "string",
                    "minLength": 1,
                    "description": "e.g. \"DEADLINE 28 NOV · 16 DAYS\", \"WON · 04 DEC\""
                  },
                  "at": {
                    "type": "string",
                    "minLength": 1,
                    "format": "date-time"
                  },
                  "days_left": {
                    "type": "integer",
                    "minimum": 0
                  }
                },
                "required": [
                  "kind",
                  "label"
                ],
                "additionalProperties": false
              },
              "pm": {
                "type": "object",
                "properties": {
                  "name": {
                    "type": "string",
                    "minLength": 1
                  },
                  "role": {
                    "type": "string",
                    "minLength": 1
                  },
                  "is_you": {
                    "type": "boolean"
                  }
                },
                "required": [
                  "name"
                ],
                "additionalProperties": false
              },
              "tabs": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "key": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "requirements",
                        "team_input",
                        "pricing",
                        "submission",
                        "outcome"
                      ]
                    },
                    "label": {
                      "type": "string",
                      "minLength": 1
                    },
                    "count": {
                      "type": "integer",
                      "minimum": 0
                    },
                    "of": {
                      "type": "integer",
                      "minimum": 0
                    },
                    "work_id": {
                      "type": "string",
                      "minLength": 1
                    },
                    "current": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "key",
                    "label"
                  ],
                  "additionalProperties": false
                }
              }
            },
            "required": [
              "reference",
              "status"
            ],
            "additionalProperties": false,
            "description": "PROPOSAL (D-RFP-OUTCOME r2): the RFP frame on every RFP board and on team input. Counts are composed by the backend; absent counts are not shown."
          },
          "workspace": {
            "type": "object",
            "properties": {
              "line_key": {
                "type": "string",
                "minLength": 1
              },
              "screen": {
                "type": "string",
                "minLength": 1,
                "description": "Approved screen id, e.g. SCR-25"
              },
              "view": {
                "type": "string",
                "minLength": 1,
                "description": "Board state, e.g. review"
              },
              "title": {
                "type": "string",
                "minLength": 1
              },
              "subtitle": {
                "type": "string",
                "minLength": 1
              },
              "status": {
                "type": "object",
                "properties": {
                  "label": {
                    "type": "string",
                    "minLength": 1
                  },
                  "tone": {
                    "type": "string",
                    "minLength": 1,
                    "enum": [
                      "neutral",
                      "person",
                      "agent",
                      "stopped",
                      "uncertain",
                      "verified",
                      "restricted"
                    ],
                    "description": "Display tone the backend assigns; the frontend maps it to the design-system tag colour and never derives it from state names"
                  }
                },
                "required": [
                  "label"
                ],
                "additionalProperties": false
              },
              "byline": {
                "type": "string",
                "minLength": 1,
                "description": "e.g. \"Report v1 · written by Tunde Bello, assembled by Tola\""
              },
              "version": {
                "type": "object",
                "properties": {
                  "label": {
                    "type": "string",
                    "minLength": 1
                  },
                  "number": {
                    "type": "integer",
                    "minimum": 1
                  },
                  "document_id": {
                    "type": "string",
                    "minLength": 1
                  }
                },
                "required": [
                  "label"
                ],
                "additionalProperties": false
              },
              "context": {
                "type": "object",
                "properties": {
                  "project": {
                    "type": "object",
                    "properties": {
                      "case_id": {
                        "type": "string",
                        "minLength": 1
                      },
                      "title": {
                        "type": "string",
                        "minLength": 1
                      }
                    },
                    "required": [
                      "case_id",
                      "title"
                    ],
                    "additionalProperties": false
                  },
                  "crumbs": {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "properties": {
                        "value": {
                          "type": "string",
                          "minLength": 1
                        },
                        "label": {
                          "type": "string",
                          "minLength": 1
                        }
                      },
                      "required": [
                        "value",
                        "label"
                      ],
                      "additionalProperties": false
                    }
                  }
                },
                "required": [],
                "additionalProperties": false
              },
              "agent_note": {
                "type": "object",
                "properties": {
                  "agent": {
                    "type": "string",
                    "minLength": 1,
                    "enum": [
                      "tola",
                      "chidi",
                      "zainab"
                    ]
                  },
                  "lines": {
                    "type": "array",
                    "items": {
                      "type": "string",
                      "minLength": 1
                    }
                  }
                },
                "required": [
                  "agent",
                  "lines"
                ],
                "additionalProperties": false
              },
              "sections": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "key": {
                      "type": "string",
                      "minLength": 1
                    },
                    "kind": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "facts",
                        "table",
                        "checklist",
                        "findings",
                        "suggestions",
                        "recipients",
                        "figures",
                        "text",
                        "timeline"
                      ]
                    },
                    "title": {
                      "type": "string",
                      "minLength": 1
                    },
                    "note": {
                      "type": "string",
                      "minLength": 1
                    },
                    "agent": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "tola",
                        "chidi",
                        "zainab"
                      ]
                    },
                    "as_of": {
                      "type": "string",
                      "minLength": 1,
                      "format": "date-time"
                    },
                    "coverage": {
                      "type": "string",
                      "minLength": 1
                    },
                    "restricted": {
                      "type": "boolean"
                    },
                    "restricted_label": {
                      "type": "string",
                      "minLength": 1
                    },
                    "columns": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "key": {
                            "type": "string",
                            "minLength": 1
                          },
                          "label": {
                            "type": "string",
                            "minLength": 1
                          },
                          "kind": {
                            "type": "string",
                            "minLength": 1,
                            "enum": [
                              "text",
                              "money",
                              "date",
                              "tag",
                              "reference",
                              "integer"
                            ]
                          }
                        },
                        "required": [
                          "key",
                          "label"
                        ],
                        "additionalProperties": false
                      }
                    },
                    "items": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "id": {
                            "type": "string",
                            "minLength": 1
                          },
                          "text": {
                            "type": "string",
                            "minLength": 1
                          },
                          "detail": {
                            "type": "string",
                            "minLength": 1
                          },
                          "label": {
                            "type": "string",
                            "minLength": 1
                          },
                          "value": {
                            "type": "string",
                            "minLength": 1
                          },
                          "money": {
                            "type": "object",
                            "properties": {
                              "amount": {
                                "type": "string",
                                "minLength": 1,
                                "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                                "description": "Decimal string; absent when unknown"
                              },
                              "currency": {
                                "type": "string",
                                "minLength": 1,
                                "pattern": "^[A-Z]{3}$"
                              },
                              "unknown": {
                                "type": "boolean"
                              }
                            },
                            "required": [
                              "currency",
                              "unknown"
                            ],
                            "additionalProperties": false,
                            "description": "Item amount. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                          },
                          "cells": {
                            "type": "array",
                            "items": {
                              "type": "object",
                              "properties": {
                                "column": {
                                  "type": "string",
                                  "minLength": 1
                                },
                                "text": {
                                  "type": "string",
                                  "minLength": 1
                                },
                                "money": {
                                  "type": "object",
                                  "properties": {
                                    "amount": {
                                      "type": "string",
                                      "minLength": 1,
                                      "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                                      "description": "Decimal string; absent when unknown"
                                    },
                                    "currency": {
                                      "type": "string",
                                      "minLength": 1,
                                      "pattern": "^[A-Z]{3}$"
                                    },
                                    "unknown": {
                                      "type": "boolean"
                                    }
                                  },
                                  "required": [
                                    "currency",
                                    "unknown"
                                  ],
                                  "additionalProperties": false,
                                  "description": "Cell amount. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                                },
                                "date": {
                                  "type": "object",
                                  "properties": {
                                    "date": {
                                      "type": "string",
                                      "minLength": 1,
                                      "format": "date"
                                    },
                                    "unknown": {
                                      "type": "boolean"
                                    }
                                  },
                                  "required": [
                                    "unknown"
                                  ],
                                  "additionalProperties": false
                                },
                                "tag": {
                                  "type": "object",
                                  "properties": {
                                    "label": {
                                      "type": "string",
                                      "minLength": 1
                                    },
                                    "tone": {
                                      "type": "string",
                                      "minLength": 1,
                                      "enum": [
                                        "neutral",
                                        "person",
                                        "agent",
                                        "stopped",
                                        "uncertain",
                                        "verified",
                                        "restricted"
                                      ],
                                      "description": "Display tone the backend assigns; the frontend maps it to the design-system tag colour and never derives it from state names"
                                    }
                                  },
                                  "required": [
                                    "label"
                                  ],
                                  "additionalProperties": false
                                },
                                "link": {
                                  "type": "object",
                                  "properties": {
                                    "label": {
                                      "type": "string",
                                      "minLength": 1
                                    },
                                    "reference": {
                                      "type": "string",
                                      "minLength": 1
                                    },
                                    "work_id": {
                                      "type": "string",
                                      "minLength": 1
                                    },
                                    "document_id": {
                                      "type": "string",
                                      "minLength": 1
                                    },
                                    "case_id": {
                                      "type": "string",
                                      "minLength": 1
                                    },
                                    "evidence_id": {
                                      "type": "string",
                                      "minLength": 1
                                    }
                                  },
                                  "required": [],
                                  "additionalProperties": false
                                },
                                "restricted": {
                                  "type": "boolean"
                                }
                              },
                              "required": [
                                "column"
                              ],
                              "additionalProperties": false
                            }
                          },
                          "status": {
                            "type": "string",
                            "minLength": 1,
                            "enum": [
                              "done",
                              "now",
                              "next",
                              "not_yet",
                              "held",
                              "blocked",
                              "unknown",
                              "not_applicable"
                            ]
                          },
                          "tag": {
                            "type": "object",
                            "properties": {
                              "label": {
                                "type": "string",
                                "minLength": 1
                              },
                              "tone": {
                                "type": "string",
                                "minLength": 1,
                                "enum": [
                                  "neutral",
                                  "person",
                                  "agent",
                                  "stopped",
                                  "uncertain",
                                  "verified",
                                  "restricted"
                                ],
                                "description": "Display tone the backend assigns; the frontend maps it to the design-system tag colour and never derives it from state names"
                              }
                            },
                            "required": [
                              "label"
                            ],
                            "additionalProperties": false
                          },
                          "severity": {
                            "type": "string",
                            "minLength": 1,
                            "enum": [
                              "high",
                              "medium",
                              "low",
                              "info"
                            ]
                          },
                          "owner": {
                            "type": "object",
                            "properties": {
                              "name": {
                                "type": "string",
                                "minLength": 1
                              },
                              "role": {
                                "type": "string",
                                "minLength": 1
                              },
                              "recorded_by_pm": {
                                "type": "boolean"
                              },
                              "outside_party": {
                                "type": "boolean"
                              }
                            },
                            "required": [
                              "name"
                            ],
                            "additionalProperties": false
                          },
                          "due": {
                            "type": "object",
                            "properties": {
                              "date": {
                                "type": "string",
                                "minLength": 1,
                                "format": "date"
                              },
                              "unknown": {
                                "type": "boolean"
                              }
                            },
                            "required": [
                              "unknown"
                            ],
                            "additionalProperties": false
                          },
                          "held_by": {
                            "type": "object",
                            "properties": {
                              "kind": {
                                "type": "string",
                                "minLength": 1,
                                "enum": [
                                  "person",
                                  "role",
                                  "agent",
                                  "outside_party",
                                  "factory"
                                ]
                              },
                              "name": {
                                "type": "string",
                                "minLength": 1,
                                "description": "Person, role, agent or outside party name as recorded"
                              },
                              "is_you": {
                                "type": "boolean"
                              }
                            },
                            "required": [
                              "kind",
                              "name",
                              "is_you"
                            ],
                            "additionalProperties": false
                          },
                          "agent": {
                            "type": "string",
                            "minLength": 1,
                            "enum": [
                              "tola",
                              "chidi",
                              "zainab"
                            ]
                          },
                          "at": {
                            "type": "string",
                            "minLength": 1,
                            "format": "date-time"
                          },
                          "cites": {
                            "type": "array",
                            "items": {
                              "type": "object",
                              "properties": {
                                "label": {
                                  "type": "string",
                                  "minLength": 1
                                },
                                "reference": {
                                  "type": "string",
                                  "minLength": 1
                                },
                                "work_id": {
                                  "type": "string",
                                  "minLength": 1
                                },
                                "document_id": {
                                  "type": "string",
                                  "minLength": 1
                                },
                                "case_id": {
                                  "type": "string",
                                  "minLength": 1
                                },
                                "evidence_id": {
                                  "type": "string",
                                  "minLength": 1
                                }
                              },
                              "required": [],
                              "additionalProperties": false
                            }
                          },
                          "cite_label": {
                            "type": "string",
                            "minLength": 1,
                            "description": "e.g. \"2 RECORDS\""
                          },
                          "channel": {
                            "type": "string",
                            "minLength": 1
                          },
                          "receipt": {
                            "type": "string",
                            "minLength": 1,
                            "enum": [
                              "received",
                              "not_yet",
                              "uncertain",
                              "failed",
                              "unknown"
                            ]
                          },
                          "restricted": {
                            "type": "boolean"
                          },
                          "steps": {
                            "type": "array",
                            "items": {
                              "type": "string",
                              "minLength": 1,
                              "description": "Keys of workspace.steps that act on this item"
                            }
                          }
                        },
                        "required": [
                          "id"
                        ],
                        "additionalProperties": false
                      }
                    },
                    "total": {
                      "type": "integer",
                      "minimum": 0
                    },
                    "filters": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "value": {
                            "type": "string",
                            "minLength": 1
                          },
                          "label": {
                            "type": "string",
                            "minLength": 1
                          }
                        },
                        "required": [
                          "value",
                          "label"
                        ],
                        "additionalProperties": false
                      }
                    },
                    "next_cursor": {
                      "type": "string",
                      "minLength": 1
                    }
                  },
                  "required": [
                    "key",
                    "kind",
                    "items"
                  ],
                  "additionalProperties": false
                }
              },
              "steps": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "key": {
                      "type": "string",
                      "minLength": 1
                    },
                    "label": {
                      "type": "string",
                      "minLength": 1
                    },
                    "emphasis": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "primary",
                        "secondary",
                        "danger"
                      ]
                    },
                    "applies_to": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "workspace",
                        "item",
                        "items"
                      ]
                    },
                    "fields": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "name": {
                            "type": "string",
                            "minLength": 1
                          },
                          "label": {
                            "type": "string",
                            "minLength": 1
                          },
                          "type": {
                            "type": "string",
                            "minLength": 1,
                            "description": "PROPOSAL (D-START-INTAKE): one of text, long_text, date, date_range, period, datetime, integer, money, choice, record, records, evidence, display. The submitted intake value per kind: text/long_text a string; date YYYY-MM-DD; date_range {from, to}; period YYYY-MM; datetime ISO 8601; integer a number; money {amount, currency, unknown} (left blank = unknown=true with no amount, never 0); choice one options[].value; record one option value from E-LINE-OPTIONS; records a list of them; evidence an evidence_id returned by E-EVIDENCE-UPLOAD on the line's case; display is shown, never sent."
                          },
                          "required": {
                            "type": "boolean"
                          },
                          "help": {
                            "type": "string",
                            "minLength": 1,
                            "description": "Hint under the field as composed by the backend, e.g. \"Only milestones marked complete, with proof, are listed.\""
                          },
                          "placeholder": {
                            "type": "string",
                            "minLength": 1
                          },
                          "options": {
                            "type": "array",
                            "items": {
                              "type": "object",
                              "properties": {
                                "value": {
                                  "type": "string",
                                  "minLength": 1
                                },
                                "label": {
                                  "type": "string",
                                  "minLength": 1
                                }
                              },
                              "required": [
                                "value",
                                "label"
                              ],
                              "additionalProperties": false
                            },
                            "description": "Fixed choices for a choice field (e.g. Audience: Internal or Client), listed by the backend."
                          },
                          "options_source": {
                            "type": "string",
                            "minLength": 1,
                            "enum": [
                              "line_options"
                            ],
                            "description": "Present on record/records fields: read the options from E-LINE-OPTIONS for this line and field"
                          },
                          "depends_on": {
                            "type": "string",
                            "minLength": 1,
                            "description": "Name of the field whose value narrows these options (e.g. milestone depends on project); sent as parent to E-LINE-OPTIONS"
                          },
                          "evidence_kind": {
                            "type": "string",
                            "minLength": 1,
                            "description": "Kind to send to E-EVIDENCE-UPLOAD for an evidence field"
                          },
                          "multiple": {
                            "type": "boolean"
                          },
                          "value": {
                            "type": "string",
                            "minLength": 1,
                            "description": "For display fields: the value shown, e.g. \"Client weekly report · test template v1\""
                          },
                          "restricted": {
                            "type": "boolean"
                          }
                        },
                        "required": [
                          "name",
                          "label",
                          "type",
                          "required"
                        ],
                        "additionalProperties": false,
                        "description": "Same descriptor as an E-LINES intake field (D-START-INTAKE): kind, label, help, options, evidence kind"
                      }
                    },
                    "confirm": {
                      "type": "string",
                      "minLength": 1
                    },
                    "consequence": {
                      "type": "string",
                      "minLength": 1,
                      "description": "Plain sentence on what the step does, e.g. \"Approving sends this exact version to Lagoon Health.\""
                    },
                    "task_id": {
                      "type": "string",
                      "minLength": 1,
                      "description": "Present when the step is a decision: use E-TASK-CLAIM/E-TASK-DECIDE on this task instead of E-WORK-STEP"
                    },
                    "claim_required": {
                      "type": "boolean"
                    },
                    "sends": {
                      "type": "boolean"
                    },
                    "disabled_reason": {
                      "type": "string",
                      "minLength": 1
                    }
                  },
                  "required": [
                    "key",
                    "label"
                  ],
                  "additionalProperties": false
                }
              },
              "next": {
                "type": "array",
                "items": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "revision": {
                "type": "integer",
                "minimum": 1
              }
            },
            "required": [
              "line_key",
              "sections"
            ],
            "additionalProperties": false,
            "description": "PROPOSAL (D-LINE-WORKSPACE): the line-specific content of the work item, one typed block for every line, rendered by section kind. Which sections and steps exist, their values and who may take each step are composed by the backend; the frontend shows only what is returned. Restricted sections carry restricted=true and no rows for people without the grant (INV-RESTRICTED); unknown amounts and dates use the unknown form, never 0."
          },
          "assign": {
            "type": "object",
            "properties": {
              "role": {
                "type": "string",
                "minLength": 1
              },
              "candidates": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "person_id": {
                      "type": "string",
                      "minLength": 1
                    },
                    "name": {
                      "type": "string",
                      "minLength": 1
                    },
                    "role": {
                      "type": "string",
                      "minLength": 1
                    },
                    "hint": {
                      "type": "string",
                      "minLength": 1,
                      "description": "e.g. current load, as the backend states it"
                    }
                  },
                  "required": [
                    "person_id",
                    "name"
                  ],
                  "additionalProperties": false
                }
              },
              "note_required": {
                "type": "boolean"
              }
            },
            "required": [
              "candidates"
            ],
            "additionalProperties": false,
            "description": "PROPOSAL (D-RFP-INTAKE): present when this person may assign the accountable person (e.g. an Unassigned RFP); candidates come from the backend's configured rule"
          }
        },
        "required": [
          "id",
          "title",
          "line",
          "reference",
          "state",
          "revision",
          "stations",
          "facts",
          "tasks",
          "agent",
          "next_step",
          "sample"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.work.read",
  "service": "workflows.factory.snapshot",
  "local_work": "Resolve the record, check grants and authority, call workflows.factory.snapshot.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-WORK-HISTORY — Work item history

```json
{
  "id": "E-WORK-HISTORY",
  "title": "Work item history",
  "refs": [
    "R-WORKITEM",
    "REC-AUDIT",
    "REC-TASK",
    "INV-ACCESS",
    "INV-AUDIT",
    "INV-RESTRICTED",
    "T-WORKITEM",
    "A-HISTORY"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
  ],
  "method": "GET",
  "path": "/api/v1/work/{work_id}/history",
  "trigger": "History tab",
  "security": [
    "Session"
  ],
  "permission": "Same as reading the work item; restricted entries returned as Restricted.",
  "parameters": [
    {
      "name": "work_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "kind",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "all",
          "decisions",
          "agent_work",
          "evidence"
        ]
      }
    },
    {
      "name": "cursor",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "limit",
      "in": "query",
      "required": false,
      "schema": {
        "type": "integer",
        "enum": [
          10,
          20,
          50
        ],
        "description": "Rows per page chosen by the person; default 20"
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Work item history",
      "schema": {
        "type": "object",
        "properties": {
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "at": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date-time"
                },
                "actor_kind": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "person",
                    "agent",
                    "factory"
                  ]
                },
                "actor": {
                  "type": "string",
                  "minLength": 1
                },
                "event": {
                  "type": "string",
                  "minLength": 1
                },
                "version": {
                  "type": "string"
                },
                "detail": {
                  "type": "string"
                },
                "restricted": {
                  "type": "boolean"
                }
              },
              "required": [
                "at",
                "actor_kind",
                "actor",
                "event",
                "restricted"
              ],
              "additionalProperties": false
            }
          },
          "next_cursor": {
            "type": "string"
          },
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          }
        },
        "required": [
          "items",
          "as_of"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.work.history",
  "service": "core.Audit query",
  "local_work": "Resolve the record, check grants and authority, call core.Audit query.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-TASK-CLAIM — Claim a task

```json
{
  "id": "E-TASK-CLAIM",
  "title": "Claim a task",
  "refs": [
    "R-DECIDE",
    "REC-TASK",
    "INV-ACCESS",
    "INV-REVISION",
    "INV-AUDIT",
    "T-DECIDE",
    "A-DECIDE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
  ],
  "method": "POST",
  "path": "/api/v1/tasks/{task_id}/claim",
  "trigger": "Open a decision you are eligible for",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "Eligible role for the task; not the preparer where separation applies.",
  "parameters": [
    {
      "name": "task_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": {
    "type": "object",
    "properties": {
      "expected_revision": {
        "type": "integer",
        "minimum": 1
      }
    },
    "required": [
      "expected_revision"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Claim a task",
      "schema": {
        "type": "object",
        "properties": {
          "task_id": {
            "type": "string",
            "minLength": 1
          },
          "revision": {
            "type": "integer",
            "minimum": 1
          },
          "claimed_by": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "task_id",
          "revision",
          "claimed_by"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named in message",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.tasks.claim",
  "service": "workflows.factory.claim_task",
  "local_work": "Resolve the record, check grants and authority, call workflows.factory.claim_task; write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-TASK-DECIDE — Decide one exact version

```json
{
  "id": "E-TASK-DECIDE",
  "title": "Decide one exact version",
  "refs": [
    "R-DECIDE",
    "REC-TASK",
    "REC-WORK",
    "REC-EVIDENCE",
    "INV-ACCESS",
    "INV-REVISION",
    "INV-AGENT",
    "INV-AUDIT",
    "T-DECIDE",
    "A-DECIDE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
  ],
  "method": "POST",
  "path": "/api/v1/tasks/{task_id}/decision",
  "trigger": "Approve, Return, Reject or Withdraw approval",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "Claimed eligible role; agents rejected.",
  "parameters": [
    {
      "name": "task_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": {
    "type": "object",
    "properties": {
      "expected_revision": {
        "type": "integer",
        "minimum": 1
      },
      "verdict": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "approve",
          "return",
          "reject",
          "revoke"
        ]
      },
      "note": {
        "type": "string",
        "description": "Up to 2000 characters; required to return, reject or withdraw"
      },
      "evidence_id": {
        "type": "string"
      }
    },
    "required": [
      "expected_revision",
      "verdict"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Decide one exact version",
      "schema": {
        "type": "object",
        "properties": {
          "task_id": {
            "type": "string",
            "minLength": 1
          },
          "verdict": {
            "type": "string",
            "minLength": 1
          },
          "decided_by": {
            "type": "string",
            "minLength": 1
          },
          "decided_at": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          },
          "work_state": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "ready",
              "processing",
              "waiting",
              "owner_needed",
              "setup_needed",
              "action_needed",
              "effect_uncertain",
              "awaiting_reconciliation",
              "verified",
              "cancelled",
              "followup_needed"
            ]
          }
        },
        "required": [
          "task_id",
          "verdict",
          "decided_by",
          "decided_at",
          "work_state"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named in message",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.tasks.decide",
  "service": "workflows.factory.decide",
  "local_work": "Resolve the record, check grants and authority, call workflows.factory.decide; write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-LINES — Lines I can start and their intake

```json
{
  "id": "E-LINES",
  "title": "Lines I can start and their intake",
  "refs": [
    "R-START",
    "REC-GRANT",
    "INV-ACCESS",
    "D-LEADERS-START",
    "T-START",
    "A-START",
    "D-START-INTAKE",
    "A-START-INTAKE"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V5",
    "S-SCREENS"
  ],
  "method": "GET",
  "path": "/api/v1/lines",
  "trigger": "Start work menu",
  "security": [
    "Session"
  ],
  "permission": "Signed in; only lines with factory.start for the person.",
  "parameters": [],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Lines I can start and their intake",
      "schema": {
        "type": "object",
        "properties": {
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "key": {
                  "type": "string",
                  "minLength": 1
                },
                "title": {
                  "type": "string",
                  "minLength": 1
                },
                "group": {
                  "type": "string",
                  "minLength": 1
                },
                "intake": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "name": {
                        "type": "string",
                        "minLength": 1
                      },
                      "label": {
                        "type": "string",
                        "minLength": 1
                      },
                      "type": {
                        "type": "string",
                        "minLength": 1,
                        "description": "PROPOSAL (D-START-INTAKE): one of text, long_text, date, date_range, period, datetime, integer, money, choice, record, records, evidence, display. The submitted intake value per kind: text/long_text a string; date YYYY-MM-DD; date_range {from, to}; period YYYY-MM; datetime ISO 8601; integer a number; money {amount, currency, unknown} (left blank = unknown=true with no amount, never 0); choice one options[].value; record one option value from E-LINE-OPTIONS; records a list of them; evidence an evidence_id returned by E-EVIDENCE-UPLOAD on the line's case; display is shown, never sent."
                      },
                      "required": {
                        "type": "boolean"
                      },
                      "help": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Hint under the field as composed by the backend, e.g. \"Only milestones marked complete, with proof, are listed.\""
                      },
                      "placeholder": {
                        "type": "string",
                        "minLength": 1
                      },
                      "options": {
                        "type": "array",
                        "items": {
                          "type": "object",
                          "properties": {
                            "value": {
                              "type": "string",
                              "minLength": 1
                            },
                            "label": {
                              "type": "string",
                              "minLength": 1
                            }
                          },
                          "required": [
                            "value",
                            "label"
                          ],
                          "additionalProperties": false
                        },
                        "description": "Fixed choices for a choice field (e.g. Audience: Internal or Client), listed by the backend."
                      },
                      "options_source": {
                        "type": "string",
                        "minLength": 1,
                        "enum": [
                          "line_options"
                        ],
                        "description": "Present on record/records fields: read the options from E-LINE-OPTIONS for this line and field"
                      },
                      "depends_on": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Name of the field whose value narrows these options (e.g. milestone depends on project); sent as parent to E-LINE-OPTIONS"
                      },
                      "evidence_kind": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Kind to send to E-EVIDENCE-UPLOAD for an evidence field"
                      },
                      "multiple": {
                        "type": "boolean"
                      },
                      "value": {
                        "type": "string",
                        "minLength": 1,
                        "description": "For display fields: the value shown, e.g. \"Client weekly report · test template v1\""
                      },
                      "restricted": {
                        "type": "boolean"
                      }
                    },
                    "required": [
                      "name",
                      "label",
                      "type",
                      "required"
                    ],
                    "additionalProperties": false
                  }
                },
                "subtitle": {
                  "type": "string",
                  "minLength": 1,
                  "description": "One line under the title in the chooser, e.g. \"From a completed milestone\""
                },
                "case_scope": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "project",
                    "fixed"
                  ],
                  "description": "project: the case is the project chosen in the intake field named by case_field; fixed: start on case_id below"
                },
                "case_field": {
                  "type": "string",
                  "minLength": 1,
                  "description": "Name of the record field whose chosen option carries case_id and case_revision (case_scope project)"
                },
                "case_id": {
                  "type": "string",
                  "minLength": 1,
                  "description": "Case to start on when case_scope is fixed (e.g. the Finance back-office case)"
                },
                "case_revision": {
                  "type": "integer",
                  "minimum": 1
                },
                "next": {
                  "type": "object",
                  "properties": {
                    "station_count": {
                      "type": "integer",
                      "minimum": 1
                    },
                    "agent": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "tola",
                        "chidi",
                        "zainab"
                      ]
                    },
                    "decided_by": {
                      "type": "array",
                      "items": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Role that decides, as configured on the line"
                      }
                    },
                    "summary": {
                      "type": "string",
                      "minLength": 1
                    },
                    "journey_url": {
                      "type": "string",
                      "minLength": 1
                    }
                  },
                  "required": [],
                  "additionalProperties": false,
                  "description": "The \"What happens next\" block. Absent fields are not shown; the frontend derives none of it from roles."
                },
                "start_via": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "work_start",
                    "finance_import"
                  ],
                  "description": "Which endpoint starts the line: E-WORK-START, or E-IMPORT for a file import line"
                }
              },
              "required": [
                "key",
                "title",
                "group",
                "intake"
              ],
              "additionalProperties": false
            }
          },
          "next_cursor": {
            "type": "string"
          },
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          },
          "default_line": {
            "type": "string",
            "minLength": 1,
            "description": "Line key the main Start work button opens directly. Absent: the button opens the menu (e.g. CEO and CTO, D-LEADERS-START)."
          }
        },
        "required": [
          "items",
          "as_of"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.lines.list",
  "service": "workflows.factory_definitions",
  "local_work": "Resolve the record, check grants and authority, call workflows.factory_definitions.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-WORK-START — Start a line

```json
{
  "id": "E-WORK-START",
  "title": "Start a line",
  "refs": [
    "R-START",
    "REC-WORK",
    "REC-EVIDENCE",
    "INV-ACCESS",
    "INV-AUDIT",
    "INV-REVISION",
    "D-LEADERS-START",
    "T-START",
    "A-START",
    "D-START-INTAKE"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V5",
    "S-SCREENS"
  ],
  "method": "POST",
  "path": "/api/v1/work",
  "trigger": "Start work drawer submit",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "factory.start on the case and the line's start permission.",
  "parameters": [],
  "request": {
    "type": "object",
    "properties": {
      "line": {
        "type": "string",
        "minLength": 1
      },
      "case_id": {
        "type": "string",
        "minLength": 1
      },
      "case_revision": {
        "type": "integer",
        "minimum": 1
      },
      "intake": {
        "type": "object",
        "additionalProperties": true,
        "description": "Field name to value, one entry per E-LINES intake field the person filled; value shapes per field type (D-START-INTAKE). Evidence values are evidence_ids uploaded to the same case before the start."
      },
      "idempotency_key": {
        "type": "string",
        "minLength": 1
      }
    },
    "required": [
      "line",
      "case_id",
      "case_revision",
      "intake",
      "idempotency_key"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "201",
      "description": "Start a line",
      "schema": {
        "type": "object",
        "properties": {
          "work_id": {
            "type": "string",
            "minLength": 1
          },
          "state": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "ready",
              "processing",
              "waiting",
              "owner_needed",
              "setup_needed",
              "action_needed",
              "effect_uncertain",
              "awaiting_reconciliation",
              "verified",
              "cancelled",
              "followup_needed"
            ]
          }
        },
        "required": [
          "work_id",
          "state"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          },
          "fields": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": {
                  "type": "string",
                  "minLength": 1
                },
                "message": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "name",
                "message"
              ],
              "additionalProperties": false
            }
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.work.start",
  "service": "workflows.factory.start",
  "local_work": "Resolve the record, check grants and authority, call workflows.factory.start; write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-EVIDENCE-UPLOAD — Upload proof

```json
{
  "id": "E-EVIDENCE-UPLOAD",
  "title": "Upload proof",
  "refs": [
    "R-RESPONSE",
    "REC-EVIDENCE",
    "INV-ACCESS",
    "INV-AUDIT",
    "T-RESPONSE",
    "A-RESPONSE",
    "D-START-INTAKE",
    "D-RESPONSE-VIEW"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V5",
    "S-SCREENS"
  ],
  "method": "POST",
  "path": "/api/v1/cases/{case_id}/evidence",
  "trigger": "File drop in a form (record a response, reconcile, Start work proof fields)",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "evidence.add on the case.",
  "parameters": [
    {
      "name": "case_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": {
    "type": "object",
    "properties": {
      "kind": {
        "type": "string",
        "minLength": 1
      },
      "filename": {
        "type": "string",
        "minLength": 1
      },
      "content_base64": {
        "type": "string",
        "minLength": 1
      },
      "case_revision": {
        "type": "integer",
        "minimum": 1
      }
    },
    "required": [
      "kind",
      "filename",
      "content_base64",
      "case_revision"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Upload proof",
      "schema": {
        "type": "object",
        "properties": {
          "evidence_id": {
            "type": "string",
            "minLength": 1
          },
          "sha256": {
            "type": "string",
            "minLength": 1,
            "pattern": "^[0-9a-f]{64}$"
          },
          "case_revision": {
            "type": "integer",
            "minimum": 1,
            "description": "The case revision after the upload; send it as case_revision on the start, response or action that follows"
          }
        },
        "required": [
          "evidence_id",
          "sha256"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named in message",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.evidence.upload",
  "service": "core.services.add_evidence",
  "local_work": "Resolve the record, check grants and authority, call core.services.add_evidence; write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-RESPONSE — Record an outside response

```json
{
  "id": "E-RESPONSE",
  "title": "Record an outside response",
  "refs": [
    "R-RESPONSE",
    "REC-TASK",
    "REC-EVIDENCE",
    "INV-ACCESS",
    "INV-REVISION",
    "INV-AUDIT",
    "T-RESPONSE",
    "A-RESPONSE",
    "D-RESPONSE-VIEW",
    "A-WORKSPACE"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V5",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "POST",
  "path": "/api/v1/tasks/{task_id}/response",
  "trigger": "Record a response form",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "Task recording role (PMO for client and team responses).",
  "parameters": [
    {
      "name": "task_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": {
    "type": "object",
    "properties": {
      "expected_revision": {
        "type": "integer",
        "minimum": 1
      },
      "who": {
        "type": "string",
        "minLength": 1
      },
      "action": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "approved",
          "changes_requested",
          "signed",
          "rejected",
          "estimate",
          "input"
        ]
      },
      "responded_at": {
        "type": "string",
        "minLength": 1,
        "format": "date-time"
      },
      "evidence_id": {
        "type": "string",
        "minLength": 1
      },
      "attested": {
        "type": "boolean"
      },
      "case_revision": {
        "type": "integer",
        "minimum": 1
      },
      "version_id": {
        "type": "string",
        "minLength": 1
      },
      "team": {
        "type": "string",
        "minLength": 1
      },
      "estimate_person_days": {
        "type": "number",
        "minimum": 0
      },
      "what": {
        "type": "string",
        "minLength": 1,
        "description": "What they gave (team input)"
      },
      "evidence_ids": {
        "type": "array",
        "items": {
          "type": "string",
          "minLength": 1,
          "description": "Further proof files beyond evidence_id (\"Add another file\")"
        }
      },
      "note": {
        "type": "string",
        "description": "Up to 2000 characters"
      },
      "received_via": {
        "type": "string",
        "minLength": 1,
        "description": "One of response.channels[].value"
      }
    },
    "required": [
      "expected_revision",
      "who",
      "action",
      "responded_at",
      "evidence_id",
      "attested"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Record an outside response",
      "schema": {
        "type": "object",
        "properties": {
          "task_id": {
            "type": "string",
            "minLength": 1
          },
          "work_state": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "ready",
              "processing",
              "waiting",
              "owner_needed",
              "setup_needed",
              "action_needed",
              "effect_uncertain",
              "awaiting_reconciliation",
              "verified",
              "cancelled",
              "followup_needed"
            ]
          },
          "revision": {
            "type": "integer",
            "minimum": 1
          },
          "recorded": {
            "type": "object",
            "properties": {
              "by": {
                "type": "object",
                "properties": {
                  "name": {
                    "type": "string",
                    "minLength": 1
                  },
                  "role": {
                    "type": "string",
                    "minLength": 1
                  },
                  "is_you": {
                    "type": "boolean"
                  }
                },
                "required": [
                  "name"
                ],
                "additionalProperties": false
              },
              "at": {
                "type": "string",
                "minLength": 1,
                "format": "date-time"
              },
              "responded_at": {
                "type": "string",
                "minLength": 1,
                "format": "date-time"
              },
              "received_via": {
                "type": "string",
                "minLength": 1,
                "description": "One of response.channels[].value"
              },
              "proof_count": {
                "type": "integer",
                "minimum": 0
              },
              "summary": {
                "type": "string",
                "minLength": 1
              }
            },
            "required": [
              "by",
              "at"
            ],
            "additionalProperties": false,
            "description": "Present once the response is recorded (success board): who recorded it, when, how it was received and how many proof files"
          },
          "next": {
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1
            }
          }
        },
        "required": [
          "task_id",
          "work_state"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named in message",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.tasks.response",
  "service": "workflows.factory.provide_information",
  "local_work": "Resolve the record, check grants and authority, call workflows.factory.provide_information; write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-WORK-ACTION — Resume, cancel or reconcile

```json
{
  "id": "E-WORK-ACTION",
  "title": "Resume, cancel or reconcile",
  "refs": [
    "R-EXCEPTION",
    "REC-WORK",
    "REC-AUDIT",
    "INV-ACCESS",
    "INV-REVISION",
    "INV-RESEND",
    "INV-AUDIT",
    "T-EXCEPTIONS",
    "A-RECONCILE",
    "D-WORK-ACTIONS-VIEW",
    "A-WORKSPACE"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V5",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "POST",
  "path": "/api/v1/work/{work_id}/actions",
  "trigger": "Exception actions",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "Operator authority on the line; reconcile needs the line's recovery authority.",
  "parameters": [
    {
      "name": "work_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": {
    "type": "object",
    "properties": {
      "expected_revision": {
        "type": "integer",
        "minimum": 1
      },
      "action": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "resume",
          "cancel",
          "reconcile"
        ]
      },
      "outcome": {
        "type": "string",
        "enum": [
          "delivered",
          "not_delivered",
          "unknown"
        ]
      },
      "evidence_id": {
        "type": "string"
      },
      "case_revision": {
        "type": "integer",
        "minimum": 1,
        "description": "Case revision returned by the proof upload, when evidence_id is sent"
      }
    },
    "required": [
      "expected_revision",
      "action"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Resume, cancel or reconcile",
      "schema": {
        "type": "object",
        "properties": {
          "work_id": {
            "type": "string",
            "minLength": 1
          },
          "state": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "ready",
              "processing",
              "waiting",
              "owner_needed",
              "setup_needed",
              "action_needed",
              "effect_uncertain",
              "awaiting_reconciliation",
              "verified",
              "cancelled",
              "followup_needed"
            ]
          },
          "revision": {
            "type": "integer",
            "minimum": 1
          }
        },
        "required": [
          "work_id",
          "state",
          "revision"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named in message",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.work.action",
  "service": "workflows.factory.manage / reconcile",
  "local_work": "Resolve the record, check grants and authority, call workflows.factory.manage / reconcile; write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-EXCEPTIONS — All exceptions

```json
{
  "id": "E-EXCEPTIONS",
  "title": "All exceptions",
  "refs": [
    "R-EXCEPTION",
    "REC-WORK",
    "INV-ACCESS",
    "D-PAGING",
    "T-EXCEPTIONS",
    "A-RESUME",
    "D-EXCEPTIONS-LIST",
    "A-EXCEPTIONS-LIST"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "GET",
  "path": "/api/v1/exceptions",
  "trigger": "Overview and All exceptions page",
  "security": [
    "Session"
  ],
  "permission": "Leads; filtered by grants.",
  "parameters": [
    {
      "name": "cursor",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "limit",
      "in": "query",
      "required": false,
      "schema": {
        "type": "integer",
        "enum": [
          10,
          20,
          50
        ],
        "description": "Rows per page chosen by the person; default 20"
      }
    },
    {
      "name": "q",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1,
        "description": "PROPOSAL (D-EXCEPTIONS-LIST): free-text search over title, reference, what is being done and who acts, across every row the person may see"
      }
    },
    {
      "name": "what",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "effect_uncertain",
          "owner_needed",
          "setup_needed",
          "blocked",
          "followup_needed"
        ],
        "description": "PROPOSAL (D-EXCEPTIONS-LIST): one kind"
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "All exceptions",
      "schema": {
        "type": "object",
        "properties": {
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "work_id": {
                  "type": "string",
                  "minLength": 1
                },
                "what": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "effect_uncertain",
                    "owner_needed",
                    "setup_needed",
                    "blocked",
                    "followup_needed"
                  ]
                },
                "title": {
                  "type": "string",
                  "minLength": 1
                },
                "doing": {
                  "type": "string",
                  "minLength": 1
                },
                "who_acts": {
                  "type": "string",
                  "minLength": 1
                },
                "since": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date-time"
                },
                "ref": {
                  "type": "string",
                  "minLength": 1,
                  "description": "The work's business reference shown under the title, e.g. INV-0412"
                }
              },
              "required": [
                "work_id",
                "what",
                "title",
                "doing",
                "who_acts",
                "since"
              ],
              "additionalProperties": false
            }
          },
          "next_cursor": {
            "type": "string"
          },
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          },
          "open_count": {
            "type": "integer",
            "minimum": 0,
            "description": "PROPOSAL (D-EXCEPTIONS-LIST): every row matching q/what the person may see, across pages (\"4 OPEN\", \"Exceptions · 4\"); absent when not counted, never guessed"
          }
        },
        "required": [
          "items",
          "as_of"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.exceptions.list",
  "service": "workflows.factory.snapshot",
  "local_work": "Resolve the record, check grants and authority, call workflows.factory.snapshot.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-PROJECTS — Projects list

```json
{
  "id": "E-PROJECTS",
  "title": "Projects list",
  "refs": [
    "R-PROJECT",
    "REC-CASE",
    "INV-ACCESS",
    "INV-SAMPLE",
    "D-PAGING",
    "T-PROJECTS",
    "A-PROJECT",
    "D-PROJECTS-VIEW",
    "A-PROJECTS-VIEW"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "GET",
  "path": "/api/v1/projects",
  "trigger": "Projects page",
  "security": [
    "Session"
  ],
  "permission": "case.read.",
  "parameters": [
    {
      "name": "q",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "cursor",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "limit",
      "in": "query",
      "required": false,
      "schema": {
        "type": "integer",
        "enum": [
          10,
          20,
          50
        ],
        "description": "Rows per page chosen by the person; default 20"
      }
    },
    {
      "name": "status",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "active",
          "closed",
          "all"
        ],
        "description": "PROPOSAL (D-PROJECTS-VIEW): the Active / Closed / All I can see tabs"
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Projects list",
      "schema": {
        "type": "object",
        "properties": {
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "case_id": {
                  "type": "string",
                  "minLength": 1
                },
                "title": {
                  "type": "string",
                  "minLength": 1
                },
                "pm": {
                  "type": "string",
                  "minLength": 1
                },
                "stage": {
                  "type": "string",
                  "minLength": 1
                },
                "sample": {
                  "type": "boolean"
                },
                "reference": {
                  "type": "string",
                  "minLength": 1
                },
                "next_milestone": {
                  "type": "object",
                  "properties": {
                    "name": {
                      "type": "string",
                      "minLength": 1
                    },
                    "due": {
                      "type": "object",
                      "properties": {
                        "date": {
                          "type": "string",
                          "minLength": 1,
                          "format": "date"
                        },
                        "unknown": {
                          "type": "boolean"
                        }
                      },
                      "required": [
                        "unknown"
                      ],
                      "additionalProperties": false
                    }
                  },
                  "required": [
                    "name"
                  ],
                  "additionalProperties": false
                },
                "needs_person": {
                  "type": "integer",
                  "minimum": 0
                },
                "stopped": {
                  "type": "integer",
                  "minimum": 0
                }
              },
              "required": [
                "case_id",
                "title",
                "pm",
                "stage",
                "sample"
              ],
              "additionalProperties": false
            }
          },
          "next_cursor": {
            "type": "string"
          },
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          },
          "counts": {
            "type": "object",
            "properties": {
              "active": {
                "type": "integer",
                "minimum": 0
              },
              "closed": {
                "type": "integer",
                "minimum": 0
              },
              "all": {
                "type": "integer",
                "minimum": 0
              }
            },
            "required": [],
            "additionalProperties": false
          },
          "total": {
            "type": "integer",
            "minimum": 0
          }
        },
        "required": [
          "items",
          "as_of"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.projects.list",
  "service": "identity.services.visible_cases",
  "local_work": "Resolve the record, check grants and authority, call identity.services.visible_cases.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-PROJECT — Project journey

```json
{
  "id": "E-PROJECT",
  "title": "Project journey",
  "refs": [
    "R-PROJECT",
    "REC-CASE",
    "REC-WORK",
    "INV-ACCESS",
    "INV-FACTS",
    "T-PROJECTS",
    "A-PROJECT",
    "D-PROJECT-TAB-ROWS",
    "D-PROJECTS-VIEW",
    "A-PROJECTS-VIEW"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V5",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "GET",
  "path": "/api/v1/projects/{case_id}",
  "trigger": "Open a project",
  "security": [
    "Session"
  ],
  "permission": "case.read.",
  "parameters": [
    {
      "name": "case_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Project journey",
      "schema": {
        "type": "object",
        "properties": {
          "case_id": {
            "type": "string",
            "minLength": 1
          },
          "title": {
            "type": "string",
            "minLength": 1
          },
          "lines": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "line": {
                  "type": "string",
                  "minLength": 1
                },
                "state": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "ready",
                    "processing",
                    "waiting",
                    "owner_needed",
                    "setup_needed",
                    "action_needed",
                    "effect_uncertain",
                    "awaiting_reconciliation",
                    "verified",
                    "cancelled",
                    "followup_needed"
                  ]
                },
                "work_id": {
                  "type": "string",
                  "minLength": 1
                },
                "reference": {
                  "type": "string",
                  "minLength": 1
                },
                "title": {
                  "type": "string",
                  "minLength": 1
                },
                "detail": {
                  "type": "string",
                  "minLength": 1,
                  "description": "e.g. \"Station 2 of 5 · client UAT\""
                },
                "station": {
                  "type": "object",
                  "properties": {
                    "index": {
                      "type": "integer",
                      "minimum": 1
                    },
                    "count": {
                      "type": "integer",
                      "minimum": 1
                    },
                    "name": {
                      "type": "string",
                      "minLength": 1
                    }
                  },
                  "required": [
                    "index",
                    "count"
                  ],
                  "additionalProperties": false
                },
                "status_label": {
                  "type": "string",
                  "minLength": 1
                },
                "tone": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "neutral",
                    "person",
                    "agent",
                    "stopped",
                    "uncertain",
                    "verified",
                    "restricted"
                  ],
                  "description": "Display tone the backend assigns; the frontend maps it to the design-system tag colour and never derives it from state names"
                }
              },
              "required": [
                "line",
                "state",
                "work_id"
              ],
              "additionalProperties": false
            }
          },
          "next": {
            "type": "string",
            "minLength": 1
          },
          "revision": {
            "type": "integer",
            "minimum": 1,
            "description": "Case revision, for starts from the project page"
          },
          "tab_counts": {
            "type": "object",
            "properties": {
              "milestones": {
                "type": "integer",
                "minimum": 0
              },
              "documents": {
                "type": "integer",
                "minimum": 0
              },
              "registers": {
                "type": "integer",
                "minimum": 0
              },
              "actions": {
                "type": "integer",
                "minimum": 0
              }
            },
            "required": [],
            "additionalProperties": false
          },
          "pm": {
            "type": "object",
            "properties": {
              "name": {
                "type": "string",
                "minLength": 1
              },
              "role": {
                "type": "string",
                "minLength": 1
              },
              "is_you": {
                "type": "boolean"
              }
            },
            "required": [
              "name"
            ],
            "additionalProperties": false
          },
          "route": {
            "type": "string",
            "minLength": 1
          },
          "work_count": {
            "type": "integer",
            "minimum": 0
          },
          "line_count": {
            "type": "integer",
            "minimum": 0
          },
          "facts": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "label": {
                  "type": "string",
                  "minLength": 1
                },
                "value": {
                  "type": "string",
                  "minLength": 1
                },
                "money": {
                  "type": "object",
                  "properties": {
                    "amount": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                      "description": "Decimal string; absent when unknown"
                    },
                    "currency": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^[A-Z]{3}$"
                    },
                    "unknown": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "currency",
                    "unknown"
                  ],
                  "additionalProperties": false,
                  "description": "Figure amount. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                },
                "unknown": {
                  "type": "boolean"
                }
              },
              "required": [
                "label"
              ],
              "additionalProperties": false
            }
          },
          "agent_summary": {
            "type": "object",
            "properties": {
              "agent": {
                "type": "string",
                "minLength": 1,
                "enum": [
                  "tola",
                  "chidi",
                  "zainab"
                ]
              },
              "text": {
                "type": "string",
                "minLength": 1
              }
            },
            "required": [
              "agent",
              "text"
            ],
            "additionalProperties": false
          },
          "delivery": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "line_key": {
                  "type": "string",
                  "minLength": 1
                },
                "title": {
                  "type": "string",
                  "minLength": 1
                },
                "state": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "ready",
                    "processing",
                    "waiting",
                    "owner_needed",
                    "setup_needed",
                    "action_needed",
                    "effect_uncertain",
                    "awaiting_reconciliation",
                    "verified",
                    "cancelled",
                    "followup_needed"
                  ]
                },
                "gate": {
                  "type": "object",
                  "properties": {
                    "label": {
                      "type": "string",
                      "minLength": 1
                    },
                    "tone": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "neutral",
                        "person",
                        "agent",
                        "stopped",
                        "uncertain",
                        "verified",
                        "restricted"
                      ],
                      "description": "Display tone the backend assigns; the frontend maps it to the design-system tag colour and never derives it from state names"
                    }
                  },
                  "required": [
                    "label"
                  ],
                  "additionalProperties": false
                },
                "work_id": {
                  "type": "string",
                  "minLength": 1
                },
                "held_by": {
                  "type": "object",
                  "properties": {
                    "kind": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "person",
                        "role",
                        "agent",
                        "outside_party",
                        "factory"
                      ]
                    },
                    "name": {
                      "type": "string",
                      "minLength": 1,
                      "description": "Person, role, agent or outside party name as recorded"
                    },
                    "is_you": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "kind",
                    "name",
                    "is_you"
                  ],
                  "additionalProperties": false
                }
              },
              "required": [
                "line_key",
                "title"
              ],
              "additionalProperties": false
            },
            "description": "PROPOSAL (D-PROJECTS-VIEW): the delivery overview (SCR-43), one row per delivery line with its gate status as the backend composes it"
          }
        },
        "required": [
          "case_id",
          "title",
          "lines",
          "next"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.projects.read",
  "service": "pmo services",
  "local_work": "Resolve the record, check grants and authority, call pmo services.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-PROJECT-TAB — Project tab

```json
{
  "id": "E-PROJECT-TAB",
  "title": "Project tab",
  "refs": [
    "R-PROJECT",
    "REC-CASE",
    "REC-MONEY",
    "REC-DOCUMENT",
    "INV-ACCESS",
    "INV-UNKNOWN",
    "INV-FACTS",
    "D-PAGING",
    "T-PROJECTS",
    "A-PROJECT",
    "D-PROJECT-TAB-ROWS",
    "A-PROJECT-TABS"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V5",
    "S-SCREENS"
  ],
  "method": "GET",
  "path": "/api/v1/projects/{case_id}/{tab}",
  "trigger": "Milestones, Documents, Money, Registers, Actions tabs",
  "security": [
    "Session"
  ],
  "permission": "case.read plus the tab's read permission (finance.read for Money).",
  "parameters": [
    {
      "name": "case_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "tab",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "milestones",
          "documents",
          "money",
          "registers",
          "actions"
        ]
      }
    },
    {
      "name": "register",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "issues",
          "changes",
          "emergencies",
          "rfps"
        ],
        "description": "Registers tab only"
      }
    },
    {
      "name": "q",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "cursor",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "limit",
      "in": "query",
      "required": false,
      "schema": {
        "type": "integer",
        "enum": [
          10,
          20,
          50
        ],
        "description": "Rows per page chosen by the person; default 20"
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Project tab",
      "schema": {
        "type": "object",
        "properties": {
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "additionalProperties": true,
              "description": "Row shape per tab, documented in handoff"
            },
            "description": "v5 untyped rows, kept for compatibility. PROPOSAL (D-PROJECT-TAB-ROWS): read the typed array named by the tab instead (milestones, documents, money, registers or actions); items holds the same rows."
          },
          "next_cursor": {
            "type": "string"
          },
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          },
          "milestones": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "position": {
                  "type": "integer",
                  "minimum": 1
                },
                "name": {
                  "type": "string",
                  "minLength": 1
                },
                "contract_amount": {
                  "type": "object",
                  "properties": {
                    "amount": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                      "description": "Decimal string; absent when unknown"
                    },
                    "currency": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^[A-Z]{3}$"
                    },
                    "unknown": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "currency",
                    "unknown"
                  ],
                  "additionalProperties": false,
                  "description": "From the signed SOW. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                },
                "amount_note": {
                  "type": "string",
                  "minLength": 1,
                  "description": "e.g. \"amount set at go-live\""
                },
                "completion": {
                  "type": "object",
                  "properties": {
                    "status": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "done",
                        "not_yet"
                      ]
                    },
                    "at": {
                      "type": "string",
                      "minLength": 1,
                      "format": "date-time"
                    },
                    "proof": {
                      "type": "string",
                      "minLength": 1,
                      "description": "Proof label, e.g. \"client UAT sign-off\""
                    },
                    "evidence_id": {
                      "type": "string",
                      "minLength": 1
                    }
                  },
                  "required": [
                    "status"
                  ],
                  "additionalProperties": false
                },
                "invoice": {
                  "type": "object",
                  "properties": {
                    "reference": {
                      "type": "string",
                      "minLength": 1
                    },
                    "title": {
                      "type": "string",
                      "minLength": 1
                    },
                    "work_id": {
                      "type": "string",
                      "minLength": 1
                    },
                    "state": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "ready",
                        "processing",
                        "waiting",
                        "owner_needed",
                        "setup_needed",
                        "action_needed",
                        "effect_uncertain",
                        "awaiting_reconciliation",
                        "verified",
                        "cancelled",
                        "followup_needed"
                      ]
                    },
                    "at": {
                      "type": "string",
                      "minLength": 1,
                      "format": "date-time"
                    }
                  },
                  "required": [
                    "reference"
                  ],
                  "additionalProperties": false
                },
                "paid": {
                  "type": "object",
                  "properties": {
                    "status": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "paid",
                        "part_paid",
                        "not_paid",
                        "not_due",
                        "finance_tracks",
                        "unknown"
                      ]
                    },
                    "owed": {
                      "type": "object",
                      "properties": {
                        "amount": {
                          "type": "string",
                          "minLength": 1,
                          "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                          "description": "Decimal string; absent when unknown"
                        },
                        "currency": {
                          "type": "string",
                          "minLength": 1,
                          "pattern": "^[A-Z]{3}$"
                        },
                        "unknown": {
                          "type": "boolean"
                        }
                      },
                      "required": [
                        "currency",
                        "unknown"
                      ],
                      "additionalProperties": false,
                      "description": "Amount still owed as recorded by Finance. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                    }
                  },
                  "required": [
                    "status"
                  ],
                  "additionalProperties": false,
                  "description": "Paid is Finance data, separate from the invoice (INV-FACTS). Composed by the backend from receipts and allocations; never derived by the frontend."
                },
                "changes": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "reference": {
                        "type": "string",
                        "minLength": 1
                      },
                      "title": {
                        "type": "string",
                        "minLength": 1
                      },
                      "amount": {
                        "type": "object",
                        "properties": {
                          "amount": {
                            "type": "string",
                            "minLength": 1,
                            "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                            "description": "Decimal string; absent when unknown"
                          },
                          "currency": {
                            "type": "string",
                            "minLength": 1,
                            "pattern": "^[A-Z]{3}$"
                          },
                          "unknown": {
                            "type": "boolean"
                          }
                        },
                        "required": [
                          "currency",
                          "unknown"
                        ],
                        "additionalProperties": false,
                        "description": "Change amount; unknown until a SOW amendment with it is signed. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                      },
                      "work_id": {
                        "type": "string",
                        "minLength": 1
                      }
                    },
                    "required": [
                      "reference",
                      "amount"
                    ],
                    "additionalProperties": false
                  }
                }
              },
              "required": [
                "position",
                "name",
                "contract_amount",
                "completion"
              ],
              "additionalProperties": false,
              "description": "Row on the milestones tab (D-PROJECT-TAB-ROWS, proposal); present only when that tab is requested."
            }
          },
          "documents": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "document_id": {
                  "type": "string",
                  "minLength": 1
                },
                "title": {
                  "type": "string",
                  "minLength": 1
                },
                "kind": {
                  "type": "string",
                  "minLength": 1
                },
                "version": {
                  "type": "string",
                  "minLength": 1
                },
                "status": {
                  "type": "string",
                  "minLength": 1
                },
                "updated_at": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date-time"
                },
                "test_template": {
                  "type": "boolean"
                },
                "work_id": {
                  "type": "string",
                  "minLength": 1
                },
                "sample": {
                  "type": "boolean"
                }
              },
              "required": [
                "document_id",
                "title",
                "version",
                "status"
              ],
              "additionalProperties": false,
              "description": "Row on the documents tab (D-PROJECT-TAB-ROWS, proposal); present only when that tab is requested."
            }
          },
          "money": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "position": {
                  "type": "integer",
                  "minimum": 1
                },
                "stage": {
                  "type": "string",
                  "minLength": 1
                },
                "amount": {
                  "type": "object",
                  "properties": {
                    "amount": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                      "description": "Decimal string; absent when unknown"
                    },
                    "currency": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^[A-Z]{3}$"
                    },
                    "unknown": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "currency",
                    "unknown"
                  ],
                  "additionalProperties": false,
                  "description": "Stage amount. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                },
                "amount_note": {
                  "type": "string",
                  "minLength": 1
                },
                "invoice": {
                  "type": "object",
                  "properties": {
                    "reference": {
                      "type": "string",
                      "minLength": 1
                    },
                    "title": {
                      "type": "string",
                      "minLength": 1
                    },
                    "work_id": {
                      "type": "string",
                      "minLength": 1
                    },
                    "state": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "ready",
                        "processing",
                        "waiting",
                        "owner_needed",
                        "setup_needed",
                        "action_needed",
                        "effect_uncertain",
                        "awaiting_reconciliation",
                        "verified",
                        "cancelled",
                        "followup_needed"
                      ]
                    },
                    "at": {
                      "type": "string",
                      "minLength": 1,
                      "format": "date-time"
                    }
                  },
                  "required": [
                    "reference"
                  ],
                  "additionalProperties": false
                },
                "invoice_status": {
                  "type": "string",
                  "minLength": 1,
                  "description": "As composed by the backend, e.g. \"Verified 03 Nov\", \"Held · owner needed\""
                },
                "paid": {
                  "type": "object",
                  "properties": {
                    "status": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "paid",
                        "part_paid",
                        "not_paid",
                        "not_due",
                        "finance_tracks",
                        "unknown"
                      ]
                    },
                    "owed": {
                      "type": "object",
                      "properties": {
                        "amount": {
                          "type": "string",
                          "minLength": 1,
                          "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                          "description": "Decimal string; absent when unknown"
                        },
                        "currency": {
                          "type": "string",
                          "minLength": 1,
                          "pattern": "^[A-Z]{3}$"
                        },
                        "unknown": {
                          "type": "boolean"
                        }
                      },
                      "required": [
                        "currency",
                        "unknown"
                      ],
                      "additionalProperties": false,
                      "description": "Amount still owed as recorded by Finance. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                    }
                  },
                  "required": [
                    "status"
                  ],
                  "additionalProperties": false,
                  "description": "Paid is Finance data, separate from the invoice (INV-FACTS). Composed by the backend from receipts and allocations; never derived by the frontend."
                },
                "figure_id": {
                  "type": "string",
                  "minLength": 1,
                  "description": "Figure in E-REPORT whose sources explain this amount"
                }
              },
              "required": [
                "position",
                "stage",
                "amount"
              ],
              "additionalProperties": false,
              "description": "Row on the money tab (D-PROJECT-TAB-ROWS, proposal); present only when that tab is requested."
            }
          },
          "registers": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "register": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "issues",
                    "changes",
                    "emergencies",
                    "rfps"
                  ]
                },
                "reference": {
                  "type": "string",
                  "minLength": 1
                },
                "title": {
                  "type": "string",
                  "minLength": 1
                },
                "severity": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "high",
                    "medium",
                    "low"
                  ],
                  "description": "Set by the PM"
                },
                "owner": {
                  "type": "object",
                  "properties": {
                    "name": {
                      "type": "string",
                      "minLength": 1
                    },
                    "role": {
                      "type": "string",
                      "minLength": 1
                    },
                    "recorded_by_pm": {
                      "type": "boolean"
                    },
                    "outside_party": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "name"
                  ],
                  "additionalProperties": false
                },
                "state": {
                  "type": "string",
                  "minLength": 1,
                  "description": "State text as composed by the backend"
                },
                "age_seconds": {
                  "type": "integer",
                  "minimum": 0
                },
                "work_id": {
                  "type": "string",
                  "minLength": 1
                },
                "sample": {
                  "type": "boolean"
                }
              },
              "required": [
                "register",
                "reference",
                "title"
              ],
              "additionalProperties": false,
              "description": "Row on the registers tab (D-PROJECT-TAB-ROWS, proposal); present only when that tab is requested."
            }
          },
          "actions": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "action_id": {
                  "type": "string",
                  "minLength": 1
                },
                "title": {
                  "type": "string",
                  "minLength": 1
                },
                "from": {
                  "type": "object",
                  "properties": {
                    "meeting": {
                      "type": "string",
                      "minLength": 1
                    },
                    "at": {
                      "type": "string",
                      "minLength": 1,
                      "format": "date"
                    }
                  },
                  "required": [
                    "meeting"
                  ],
                  "additionalProperties": false
                },
                "owner": {
                  "type": "object",
                  "properties": {
                    "name": {
                      "type": "string",
                      "minLength": 1
                    },
                    "role": {
                      "type": "string",
                      "minLength": 1
                    },
                    "recorded_by_pm": {
                      "type": "boolean"
                    },
                    "outside_party": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "name"
                  ],
                  "additionalProperties": false
                },
                "due": {
                  "type": "object",
                  "properties": {
                    "date": {
                      "type": "string",
                      "minLength": 1,
                      "format": "date"
                    },
                    "unknown": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "unknown"
                  ],
                  "additionalProperties": false
                },
                "state": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "open",
                    "overdue",
                    "done"
                  ]
                },
                "work_id": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "action_id",
                "title",
                "state"
              ],
              "additionalProperties": false,
              "description": "Row on the actions tab (D-PROJECT-TAB-ROWS, proposal); present only when that tab is requested."
            }
          },
          "summary": {
            "type": "object",
            "properties": {
              "registers": {
                "type": "object",
                "properties": {
                  "issues": {
                    "type": "integer",
                    "minimum": 0
                  },
                  "changes": {
                    "type": "integer",
                    "minimum": 0
                  },
                  "emergencies": {
                    "type": "integer",
                    "minimum": 0
                  },
                  "rfps": {
                    "type": "integer",
                    "minimum": 0
                  }
                },
                "required": [],
                "additionalProperties": false
              },
              "actions": {
                "type": "object",
                "properties": {
                  "total": {
                    "type": "integer",
                    "minimum": 0
                  },
                  "overdue": {
                    "type": "integer",
                    "minimum": 0
                  },
                  "without_owner": {
                    "type": "integer",
                    "minimum": 0
                  }
                },
                "required": [],
                "additionalProperties": false
              },
              "report_id": {
                "type": "string",
                "minLength": 1,
                "description": "Money tab: E-REPORT id for the drill-down"
              }
            },
            "required": [],
            "additionalProperties": false
          }
        },
        "required": [
          "items",
          "as_of"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.projects.tab",
  "service": "pmo / finance / documents services",
  "local_work": "Resolve the record, check grants and authority, call pmo / finance / documents services.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-DOCUMENT — Read a document version

```json
{
  "id": "E-DOCUMENT",
  "title": "Read a document version",
  "refs": [
    "R-PROJECT",
    "REC-DOCUMENT",
    "INV-ACCESS",
    "INV-SAMPLE",
    "T-PROJECTS",
    "A-PROJECT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
  ],
  "method": "GET",
  "path": "/api/v1/documents/{document_id}/versions/{version}",
  "trigger": "Document review",
  "security": [
    "Session"
  ],
  "permission": "case.read and document read.",
  "parameters": [
    {
      "name": "document_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "version",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Read a document version",
      "schema": {
        "type": "object",
        "properties": {
          "document_id": {
            "type": "string",
            "minLength": 1
          },
          "version": {
            "type": "string",
            "minLength": 1
          },
          "title": {
            "type": "string",
            "minLength": 1
          },
          "status": {
            "type": "string",
            "minLength": 1
          },
          "template": {
            "type": "string",
            "minLength": 1
          },
          "body_url": {
            "type": "string",
            "minLength": 1
          },
          "test_template": {
            "type": "boolean"
          }
        },
        "required": [
          "document_id",
          "version",
          "title",
          "status",
          "template",
          "body_url",
          "test_template"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.documents.read",
  "service": "documents services",
  "local_work": "Resolve the record, check grants and authority, call documents services.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-OVERVIEW — Factory floor

```json
{
  "id": "E-OVERVIEW",
  "title": "Factory floor",
  "refs": [
    "R-OVERVIEW",
    "REC-WORK",
    "INV-ACCESS",
    "D-UPDATES",
    "T-FLOOR",
    "A-OVERVIEW",
    "D-OVERVIEW-VIEW",
    "A-OVERVIEW-LINES"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "GET",
  "path": "/api/v1/overview",
  "trigger": "Overview page",
  "security": [
    "Session"
  ],
  "permission": "Leads, CEO, CTO; counts from visible records.",
  "parameters": [],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Factory floor",
      "schema": {
        "type": "object",
        "properties": {
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          },
          "totals": {
            "type": "object",
            "properties": {
              "in_progress": {
                "type": "integer",
                "minimum": 0
              },
              "need_a_person": {
                "type": "integer",
                "minimum": 0
              },
              "stopped": {
                "type": "integer",
                "minimum": 0
              },
              "verified_this_month": {
                "type": "integer",
                "minimum": 0
              }
            },
            "required": [
              "in_progress",
              "need_a_person",
              "stopped",
              "verified_this_month"
            ],
            "additionalProperties": false
          },
          "lines": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "line": {
                  "type": "string",
                  "minLength": 1
                },
                "stations": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "name": {
                        "type": "string",
                        "minLength": 1
                      },
                      "count": {
                        "type": "integer",
                        "minimum": 0
                      },
                      "needs_person": {
                        "type": "boolean"
                      }
                    },
                    "required": [
                      "name",
                      "count",
                      "needs_person"
                    ],
                    "additionalProperties": false
                  }
                },
                "note": {
                  "type": "string",
                  "minLength": 1
                },
                "key": {
                  "type": "string",
                  "minLength": 1
                },
                "subtitle": {
                  "type": "string",
                  "minLength": 1,
                  "description": "e.g. \"RFP · commercial\""
                },
                "agent": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "tola",
                    "chidi",
                    "zainab"
                  ]
                },
                "status": {
                  "type": "object",
                  "properties": {
                    "label": {
                      "type": "string",
                      "minLength": 1
                    },
                    "tone": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "neutral",
                        "person",
                        "agent",
                        "stopped",
                        "uncertain",
                        "verified",
                        "restricted"
                      ],
                      "description": "Display tone the backend assigns; the frontend maps it to the design-system tag colour and never derives it from state names"
                    }
                  },
                  "required": [
                    "label"
                  ],
                  "additionalProperties": false
                }
              },
              "required": [
                "line",
                "stations",
                "note"
              ],
              "additionalProperties": false
            }
          }
        },
        "required": [
          "as_of",
          "totals",
          "lines"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.overview.read",
  "service": "workflows.factory.snapshot",
  "local_work": "Resolve the record, check grants and authority, call workflows.factory.snapshot.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-MONTH-END — Month-end checklist

```json
{
  "id": "E-MONTH-END",
  "title": "Month-end checklist",
  "refs": [
    "R-FINANCE",
    "REC-MONEY",
    "REC-WORK",
    "INV-ACCESS",
    "INV-UNKNOWN",
    "INV-RESTRICTED",
    "T-FINANCE",
    "A-MONTHEND",
    "D-MONTH-END-VIEW",
    "A-MONTHEND-VIEW"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "GET",
  "path": "/api/v1/finance/month-end",
  "trigger": "Month-end page",
  "security": [
    "Session"
  ],
  "permission": "finance.read.",
  "parameters": [
    {
      "name": "period",
      "in": "query",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1,
        "pattern": "^[0-9]{4}-[0-9]{2}$"
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Month-end checklist",
      "schema": {
        "type": "object",
        "properties": {
          "period": {
            "type": "string",
            "minLength": 1
          },
          "tasks": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "line": {
                  "type": "string",
                  "minLength": 1
                },
                "state": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "ready",
                    "processing",
                    "waiting",
                    "owner_needed",
                    "setup_needed",
                    "action_needed",
                    "effect_uncertain",
                    "awaiting_reconciliation",
                    "verified",
                    "cancelled",
                    "followup_needed"
                  ]
                },
                "where": {
                  "type": "string",
                  "minLength": 1
                },
                "work_id": {
                  "type": "string"
                },
                "title": {
                  "type": "string",
                  "minLength": 1
                },
                "detail": {
                  "type": "string",
                  "minLength": 1
                },
                "status_label": {
                  "type": "string",
                  "minLength": 1
                },
                "tone": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "neutral",
                    "person",
                    "agent",
                    "stopped",
                    "uncertain",
                    "verified",
                    "restricted"
                  ],
                  "description": "Display tone the backend assigns; the frontend maps it to the design-system tag colour and never derives it from state names"
                },
                "restricted": {
                  "type": "boolean"
                },
                "restricted_label": {
                  "type": "string",
                  "minLength": 1,
                  "description": "e.g. \"HR only\"; restricted rows carry no work_id"
                }
              },
              "required": [
                "line",
                "state",
                "where"
              ],
              "additionalProperties": false
            }
          },
          "cash_received": {
            "type": "object",
            "properties": {
              "amount": {
                "type": "string",
                "minLength": 1,
                "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                "description": "Decimal string; absent when unknown"
              },
              "currency": {
                "type": "string",
                "minLength": 1,
                "pattern": "^[A-Z]{3}$"
              },
              "unknown": {
                "type": "boolean"
              }
            },
            "required": [
              "currency",
              "unknown"
            ],
            "additionalProperties": false
          },
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          },
          "coverage": {
            "type": "string",
            "minLength": 1,
            "description": "e.g. \"FROM RECORDS YOU CAN SEE\""
          },
          "summary": {
            "type": "object",
            "properties": {
              "done": {
                "type": "integer",
                "minimum": 0
              },
              "waiting": {
                "type": "integer",
                "minimum": 0
              },
              "in_progress": {
                "type": "integer",
                "minimum": 0
              },
              "total": {
                "type": "integer",
                "minimum": 0
              }
            },
            "required": [],
            "additionalProperties": false,
            "description": "Counts composed by the backend; the frontend never buckets task states itself"
          },
          "cash_received_detail": {
            "type": "object",
            "properties": {
              "known": {
                "type": "object",
                "properties": {
                  "amount": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                    "description": "Decimal string; absent when unknown"
                  },
                  "currency": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": "^[A-Z]{3}$"
                  },
                  "unknown": {
                    "type": "boolean"
                  }
                },
                "required": [
                  "currency",
                  "unknown"
                ],
                "additionalProperties": false,
                "description": "The part of cash received that is known. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
              },
              "has_unknown": {
                "type": "boolean"
              },
              "unknown_note": {
                "type": "string",
                "minLength": 1
              }
            },
            "required": [
              "has_unknown"
            ],
            "additionalProperties": false,
            "description": "Known part plus an Unknown marker (\"₦4.7M + Unknown\"); has_unknown true means some cash is not yet known, never 0 (INV-UNKNOWN)"
          },
          "agent_note": {
            "type": "object",
            "properties": {
              "agent": {
                "type": "string",
                "minLength": 1,
                "enum": [
                  "tola",
                  "chidi",
                  "zainab"
                ]
              },
              "text": {
                "type": "string",
                "minLength": 1
              }
            },
            "required": [
              "agent",
              "text"
            ],
            "additionalProperties": false
          },
          "next_action": {
            "type": "object",
            "properties": {
              "label": {
                "type": "string",
                "minLength": 1
              },
              "work_id": {
                "type": "string",
                "minLength": 1
              }
            },
            "required": [
              "label"
            ],
            "additionalProperties": false
          }
        },
        "required": [
          "period",
          "tasks",
          "cash_received"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.finance.month_end",
  "service": "finance services",
  "local_work": "Resolve the record, check grants and authority, call finance services.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-IMPORT — Submit an accounting or bank file

```json
{
  "id": "E-IMPORT",
  "title": "Submit an accounting or bank file",
  "refs": [
    "R-FINANCE",
    "REC-EVIDENCE",
    "REC-WORK",
    "INV-ACCESS",
    "INV-AUDIT",
    "INV-UNKNOWN",
    "T-FINANCE",
    "A-MONTHEND"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
  ],
  "method": "POST",
  "path": "/api/v1/cases/{case_id}/finance/imports",
  "trigger": "Import and reconcile, accounts start form",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "finance.import, finance.validate, evidence.add.",
  "parameters": [
    {
      "name": "case_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": {
    "type": "object",
    "properties": {
      "evidence_id": {
        "type": "string",
        "minLength": 1
      },
      "period": {
        "type": "string",
        "minLength": 1,
        "pattern": "^[0-9]{4}-[0-9]{2}$"
      },
      "currency": {
        "type": "string",
        "minLength": 1,
        "pattern": "^[A-Z]{3}$"
      },
      "completeness": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "complete",
          "partial",
          "unknown"
        ]
      },
      "submission_key": {
        "type": "string",
        "minLength": 1
      }
    },
    "required": [
      "evidence_id",
      "period",
      "currency",
      "completeness",
      "submission_key"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Submit an accounting or bank file",
      "schema": {
        "type": "object",
        "properties": {
          "receipt": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "started",
              "quarantined",
              "configuration_needed",
              "source_units_needed",
              "followup_needed"
            ]
          },
          "work_id": {
            "type": "string"
          },
          "findings": {
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1
            }
          }
        },
        "required": [
          "receipt",
          "findings"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named in message",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.finance.import",
  "service": "workflows.factory_accounting_intake",
  "local_work": "Resolve the record, check grants and authority, call workflows.factory_accounting_intake; write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-PAYROLL-MATCH — Payroll staff match (restricted)

```json
{
  "id": "E-PAYROLL-MATCH",
  "title": "Payroll staff match (restricted)",
  "refs": [
    "R-FINANCE",
    "REC-WORK",
    "INV-ACCESS",
    "INV-RESTRICTED",
    "T-PAYROLL",
    "A-PAYROLL"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
  ],
  "method": "GET",
  "path": "/api/v1/payroll/{work_id}/match",
  "trigger": "Payroll match screen",
  "security": [
    "Session"
  ],
  "permission": "payroll.read and payroll.private.read; HR roles only.",
  "parameters": [
    {
      "name": "work_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Payroll staff match (restricted)",
      "schema": {
        "type": "object",
        "properties": {
          "matched": {
            "type": "integer",
            "minimum": 0
          },
          "unmatched": {
            "type": "integer",
            "minimum": 0
          },
          "conflicts": {
            "type": "integer",
            "minimum": 0
          },
          "rows": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "staff": {
                  "type": "string",
                  "minLength": 1
                },
                "payroll": {
                  "type": "object",
                  "properties": {
                    "amount": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                      "description": "Decimal string; absent when unknown"
                    },
                    "currency": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^[A-Z]{3}$"
                    },
                    "unknown": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "currency",
                    "unknown"
                  ],
                  "additionalProperties": false
                },
                "hr_record": {
                  "type": "string",
                  "minLength": 1
                },
                "business_unit": {
                  "type": "string",
                  "minLength": 1
                },
                "result": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "staff",
                "payroll",
                "hr_record",
                "business_unit",
                "result"
              ],
              "additionalProperties": false
            }
          }
        },
        "required": [
          "matched",
          "unmatched",
          "conflicts",
          "rows"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.payroll.match",
  "service": "finance payroll services",
  "local_work": "Resolve the record, check grants and authority, call finance payroll services.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-SETUP-RULES — Rules and their values

```json
{
  "id": "E-SETUP-RULES",
  "title": "Rules and their values",
  "refs": [
    "R-SETUP",
    "REC-CONFIG",
    "INV-ACCESS",
    "T-SETUP",
    "A-SETUP",
    "D-SETUP-RULES-VIEW",
    "A-SETUP-RULES-VIEW"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "GET",
  "path": "/api/v1/setup/rules",
  "trigger": "Setup rules, Finance rules",
  "security": [
    "Session"
  ],
  "permission": "policy read for the area; Leads.",
  "parameters": [
    {
      "name": "area",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Rules and their values",
      "schema": {
        "type": "object",
        "properties": {
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "component": {
                  "type": "string",
                  "minLength": 1
                },
                "name": {
                  "type": "string",
                  "minLength": 1
                },
                "value": {
                  "type": "object",
                  "additionalProperties": true
                },
                "set": {
                  "type": "boolean"
                },
                "revision": {
                  "type": "integer",
                  "minimum": 0
                },
                "area": {
                  "type": "string",
                  "minLength": 1
                },
                "area_label": {
                  "type": "string",
                  "minLength": 1
                },
                "group": {
                  "type": "string",
                  "minLength": 1
                },
                "group_label": {
                  "type": "string",
                  "minLength": 1
                },
                "used_by": {
                  "type": "array",
                  "items": {
                    "type": "string",
                    "minLength": 1
                  }
                },
                "display_value": {
                  "type": "string",
                  "minLength": 1,
                  "description": "Current value as text; absent when not set (the screen shows Not set)"
                },
                "link": {
                  "type": "string",
                  "minLength": 1,
                  "description": "Screen the rule is edited on instead, e.g. costing-rule"
                },
                "holds_work": {
                  "type": "boolean"
                },
                "effective_from": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date-time"
                },
                "can_change": {
                  "type": "boolean"
                },
                "restricted": {
                  "type": "boolean"
                },
                "editor": {
                  "type": "object",
                  "properties": {
                    "kind": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "role_set",
                        "read_only"
                      ]
                    },
                    "options": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "role": {
                            "type": "string",
                            "minLength": 1
                          },
                          "label": {
                            "type": "string",
                            "minLength": 1
                          }
                        },
                        "required": [
                          "role",
                          "label"
                        ],
                        "additionalProperties": false
                      }
                    },
                    "selected": {
                      "type": "array",
                      "items": {
                        "type": "string",
                        "minLength": 1
                      }
                    }
                  },
                  "required": [
                    "kind"
                  ],
                  "additionalProperties": false
                }
              },
              "required": [
                "component",
                "name",
                "set",
                "revision"
              ],
              "additionalProperties": false
            }
          },
          "next_cursor": {
            "type": "string"
          },
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          },
          "not_set_count": {
            "type": "integer",
            "minimum": 0
          },
          "roles_missing_count": {
            "type": "integer",
            "minimum": 0
          }
        },
        "required": [
          "items",
          "as_of"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.setup.rules",
  "service": "policy.services.resolve",
  "local_work": "Resolve the record, check grants and authority, call policy.services.resolve.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-SETUP-RULE-SAVE — Save a rule as a new version

```json
{
  "id": "E-SETUP-RULE-SAVE",
  "title": "Save a rule as a new version",
  "refs": [
    "R-SETUP",
    "REC-CONFIG",
    "REC-AUDIT",
    "INV-ACCESS",
    "INV-REVISION",
    "INV-AUDIT",
    "T-SETUP",
    "A-SETUP",
    "D-SETUP-RULES-VIEW",
    "A-SETUP-RULES-VIEW"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "PUT",
  "path": "/api/v1/setup/rules/{component}",
  "trigger": "Setup rule form",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "policy.activate for the area.",
  "parameters": [
    {
      "name": "component",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": {
    "type": "object",
    "properties": {
      "expected_revision": {
        "type": "integer",
        "minimum": 0,
        "description": "PROPOSAL (D-SETUP-RULES-VIEW): the revision exactly as read; 0 saves the first version of a rule that is Not set (fixes the v6 minimum of 1, which made a first save impossible)"
      },
      "value": {
        "type": "object",
        "additionalProperties": true
      },
      "starts": {
        "type": "string",
        "minLength": 1,
        "format": "date"
      },
      "reason": {
        "type": "string",
        "minLength": 1
      },
      "evidence_id": {
        "type": "string",
        "minLength": 1
      }
    },
    "required": [
      "expected_revision",
      "value"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Save a rule as a new version",
      "schema": {
        "type": "object",
        "properties": {
          "component": {
            "type": "string",
            "minLength": 1
          },
          "revision": {
            "type": "integer",
            "minimum": 1
          }
        },
        "required": [
          "component",
          "revision"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named in message",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.setup.rule_save",
  "service": "policy.services.transition",
  "local_work": "Resolve the record, check grants and authority, call policy.services.transition; write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-PEOPLE — People and roles

```json
{
  "id": "E-PEOPLE",
  "title": "People and roles",
  "refs": [
    "R-SETUP",
    "REC-GRANT",
    "INV-ACCESS",
    "D-PAGING",
    "T-SETUP",
    "A-SETUP",
    "D-PEOPLE-VIEW",
    "A-PEOPLE-ADMIN"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "GET",
  "path": "/api/v1/setup/people",
  "trigger": "Setup people",
  "security": [
    "Session"
  ],
  "permission": "Admin.",
  "parameters": [
    {
      "name": "cursor",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "limit",
      "in": "query",
      "required": false,
      "schema": {
        "type": "integer",
        "enum": [
          10,
          20,
          50
        ],
        "description": "Rows per page chosen by the person; default 20"
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "People and roles",
      "schema": {
        "type": "object",
        "properties": {
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "person": {
                  "type": "string",
                  "minLength": 1
                },
                "roles": {
                  "type": "array",
                  "items": {
                    "type": "string",
                    "minLength": 1
                  }
                },
                "active": {
                  "type": "boolean"
                },
                "person_id": {
                  "type": "string",
                  "minLength": 1
                },
                "email": {
                  "type": "string",
                  "minLength": 1,
                  "description": "As the backend returns it"
                },
                "scopes": {
                  "type": "array",
                  "items": {
                    "type": "string",
                    "minLength": 1
                  }
                },
                "state": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "active",
                    "invited",
                    "deactivated"
                  ]
                },
                "last_signed_in_at": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date-time"
                },
                "open_items": {
                  "type": "integer",
                  "minimum": 0
                },
                "can_change": {
                  "type": "boolean"
                },
                "revision": {
                  "type": "integer",
                  "minimum": 1
                }
              },
              "required": [
                "person",
                "roles",
                "active"
              ],
              "additionalProperties": false
            }
          },
          "next_cursor": {
            "type": "string"
          },
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          },
          "roles_missing": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "role": {
                  "type": "string",
                  "minLength": 1
                },
                "label": {
                  "type": "string",
                  "minLength": 1
                },
                "held_work": {
                  "type": "integer",
                  "minimum": 0
                }
              },
              "required": [
                "role",
                "label"
              ],
              "additionalProperties": false
            }
          },
          "role_options": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "role": {
                  "type": "string",
                  "minLength": 1
                },
                "label": {
                  "type": "string",
                  "minLength": 1
                },
                "scope_needed": {
                  "type": "boolean"
                }
              },
              "required": [
                "role",
                "label"
              ],
              "additionalProperties": false
            }
          }
        },
        "required": [
          "items",
          "as_of"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.setup.people",
  "service": "identity services",
  "local_work": "Resolve the record, check grants and authority, call identity services.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-DELEGATION — Set a delegate

```json
{
  "id": "E-DELEGATION",
  "title": "Set a delegate",
  "refs": [
    "R-SETUP",
    "REC-CONFIG",
    "REC-AUDIT",
    "INV-ACCESS",
    "INV-REVISION",
    "INV-AUDIT",
    "T-SETUP",
    "A-SETUP",
    "D-DELEGATION-VIEW",
    "A-DELEGATIONS"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "PUT",
  "path": "/api/v1/setup/delegation",
  "trigger": "Delegation form",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "Leads for their own authority.",
  "parameters": [],
  "request": {
    "type": "object",
    "properties": {
      "expected_revision": {
        "type": "integer",
        "minimum": 1
      },
      "delegate": {
        "type": "string",
        "minLength": 1
      },
      "starts": {
        "type": "string",
        "minLength": 1,
        "format": "date"
      },
      "ends": {
        "type": "string",
        "minLength": 1,
        "format": "date"
      },
      "authority": {
        "type": "string",
        "minLength": 1,
        "description": "One of E-DELEGATIONS authorities[].value"
      },
      "reason": {
        "type": "string",
        "minLength": 1
      }
    },
    "required": [
      "expected_revision",
      "delegate",
      "starts",
      "ends"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Set a delegate",
      "schema": {
        "type": "object",
        "properties": {
          "revision": {
            "type": "integer",
            "minimum": 1
          }
        },
        "required": [
          "revision"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named in message",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.setup.delegation",
  "service": "policy.role_assignments",
  "local_work": "Resolve the record, check grants and authority, call policy.role_assignments; write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-TEMPLATES — Document templates

```json
{
  "id": "E-TEMPLATES",
  "title": "Document templates",
  "refs": [
    "R-SETUP",
    "REC-DOCUMENT",
    "INV-ACCESS",
    "INV-SAMPLE",
    "T-SETUP",
    "A-SETUP",
    "D-TEMPLATES-VIEW",
    "A-TEMPLATE-VERSION"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "GET",
  "path": "/api/v1/setup/templates",
  "trigger": "Setup templates",
  "security": [
    "Session"
  ],
  "permission": "documents read.",
  "parameters": [],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Document templates",
      "schema": {
        "type": "object",
        "properties": {
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "line": {
                  "type": "string",
                  "minLength": 1
                },
                "name": {
                  "type": "string",
                  "minLength": 1
                },
                "version": {
                  "type": "string",
                  "minLength": 1
                },
                "test_template": {
                  "type": "boolean"
                },
                "template_id": {
                  "type": "string",
                  "minLength": 1
                },
                "kind": {
                  "type": "string",
                  "minLength": 1
                },
                "updated_at": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date-time"
                },
                "updated_by": {
                  "type": "string",
                  "minLength": 1
                },
                "versions": {
                  "type": "integer",
                  "minimum": 0
                },
                "revision": {
                  "type": "integer",
                  "minimum": 1
                },
                "can_upload": {
                  "type": "boolean"
                }
              },
              "required": [
                "line",
                "name",
                "version",
                "test_template"
              ],
              "additionalProperties": false
            }
          },
          "next_cursor": {
            "type": "string"
          },
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          }
        },
        "required": [
          "items",
          "as_of"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.setup.templates",
  "service": "documents services",
  "local_work": "Resolve the record, check grants and authority, call documents services.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-NOTIFICATIONS — Notification centre

```json
{
  "id": "E-NOTIFICATIONS",
  "title": "Notification centre",
  "refs": [
    "R-ALERTS",
    "REC-NOTIFICATION",
    "INV-ACCESS",
    "D-NOTIFY-MODEL",
    "D-PAGING",
    "T-ALERTS",
    "A-ALERTS",
    "D-ALERT-PREFS-VIEW",
    "A-NOTIFICATIONS"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "GET",
  "path": "/api/v1/notifications",
  "trigger": "Bell and notifications page",
  "security": [
    "Session"
  ],
  "permission": "Own notifications only.",
  "parameters": [
    {
      "name": "cursor",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "limit",
      "in": "query",
      "required": false,
      "schema": {
        "type": "integer",
        "enum": [
          10,
          20,
          50
        ],
        "description": "Rows per page chosen by the person; default 20"
      }
    },
    {
      "name": "q",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1,
        "description": "PROPOSAL (D-ALERT-PREFS-VIEW): search over the alert text and reference"
      }
    },
    {
      "name": "agent",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "tola",
          "chidi",
          "zainab"
        ]
      }
    },
    {
      "name": "unread",
      "in": "query",
      "required": false,
      "schema": {
        "type": "boolean"
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Notification centre",
      "schema": {
        "type": "object",
        "properties": {
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "id": {
                  "type": "string",
                  "minLength": 1
                },
                "work_id": {
                  "type": "string",
                  "minLength": 1
                },
                "agent": {
                  "type": "string",
                  "minLength": 1
                },
                "text": {
                  "type": "string",
                  "minLength": 1
                },
                "at": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date-time"
                },
                "read": {
                  "type": "boolean"
                },
                "reference": {
                  "type": "string",
                  "minLength": 1
                },
                "delivered_via": {
                  "type": "array",
                  "items": {
                    "type": "string",
                    "minLength": 1,
                    "enum": [
                      "whatsapp",
                      "email",
                      "in_app"
                    ]
                  }
                },
                "delivered_at": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date-time"
                },
                "digest_at": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date-time"
                },
                "in_app_reason": {
                  "type": "string",
                  "minLength": 1,
                  "description": "e.g. \"you are not HR\": why this alert was shown in the app only"
                }
              },
              "required": [
                "id",
                "work_id",
                "agent",
                "text",
                "at",
                "read"
              ],
              "additionalProperties": false
            }
          },
          "next_cursor": {
            "type": "string"
          },
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          },
          "total": {
            "type": "integer",
            "minimum": 0
          },
          "unread_count": {
            "type": "integer",
            "minimum": 0
          }
        },
        "required": [
          "items",
          "as_of"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.notifications.list",
  "service": "api notifications (new)",
  "local_work": "Resolve the record, check grants and authority, call api notifications (new).",
  "integration_calls": [
    {
      "integration": "I-ALERTS",
      "operation": "queue_alert"
    }
  ],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-ALERT-PREFS — My alert preferences

```json
{
  "id": "E-ALERT-PREFS",
  "title": "My alert preferences",
  "refs": [
    "R-ALERTS",
    "REC-ALERT-PREF",
    "REC-AUDIT",
    "INV-ACCESS",
    "INV-AUDIT",
    "D-NOTIFY-MODEL",
    "D-ALERT-PROVIDERS",
    "T-ALERTS",
    "A-ALERTS",
    "D-ALERT-PREFS-VIEW",
    "A-ALERT-PREFS"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "PUT",
  "path": "/api/v1/me/alert-preferences",
  "trigger": "Notification settings",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "Own preferences only.",
  "parameters": [],
  "request": {
    "type": "object",
    "properties": {
      "channel": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "whatsapp",
          "email",
          "both",
          "none"
        ],
        "description": "v6 summary field, kept: the backend derives per-event values from it only when events is absent"
      },
      "frequency": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "immediate",
          "daily"
        ]
      },
      "expected_revision": {
        "type": "integer",
        "minimum": 0
      },
      "events": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "key": {
              "type": "string",
              "minLength": 1
            },
            "whatsapp": {
              "type": "boolean"
            },
            "email": {
              "type": "boolean"
            }
          },
          "required": [
            "key"
          ],
          "additionalProperties": false
        }
      },
      "digest_at": {
        "type": "string",
        "minLength": 1,
        "pattern": "^[0-2][0-9]:[0-5][0-9]$"
      },
      "quiet_hours": {
        "type": "string",
        "minLength": 1
      }
    },
    "required": [
      "channel",
      "frequency"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "My alert preferences",
      "schema": {
        "type": "object",
        "properties": {
          "channel": {
            "type": "string",
            "minLength": 1
          },
          "frequency": {
            "type": "string",
            "minLength": 1
          },
          "revision": {
            "type": "integer",
            "minimum": 1
          },
          "events": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "key": {
                  "type": "string",
                  "minLength": 1
                },
                "label": {
                  "type": "string",
                  "minLength": 1
                },
                "whatsapp": {
                  "type": "boolean"
                },
                "email": {
                  "type": "boolean"
                },
                "timing": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "immediate",
                    "daily_digest"
                  ]
                },
                "timing_label": {
                  "type": "string",
                  "minLength": 1
                },
                "locked_reason": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "key",
                "label",
                "whatsapp",
                "email"
              ],
              "additionalProperties": false
            }
          },
          "digest_at": {
            "type": "object",
            "properties": {
              "value": {
                "type": "string",
                "minLength": 1,
                "pattern": "^[0-2][0-9]:[0-5][0-9]$"
              },
              "options": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "value": {
                      "type": "string",
                      "minLength": 1
                    },
                    "label": {
                      "type": "string",
                      "minLength": 1
                    }
                  },
                  "required": [
                    "value",
                    "label"
                  ],
                  "additionalProperties": false
                }
              }
            },
            "required": [
              "options"
            ],
            "additionalProperties": false
          },
          "quiet_hours": {
            "type": "object",
            "properties": {
              "value": {
                "type": "string",
                "minLength": 1
              },
              "options": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "value": {
                      "type": "string",
                      "minLength": 1
                    },
                    "label": {
                      "type": "string",
                      "minLength": 1
                    }
                  },
                  "required": [
                    "value",
                    "label"
                  ],
                  "additionalProperties": false
                }
              }
            },
            "required": [
              "options"
            ],
            "additionalProperties": false
          },
          "whatsapp": {
            "type": "object",
            "properties": {
              "masked_number": {
                "type": "string",
                "minLength": 1,
                "description": "e.g. \"+234 803 *** 4412\"; never unmasked"
              },
              "verified": {
                "type": "boolean"
              }
            },
            "required": [
              "verified"
            ],
            "additionalProperties": false
          },
          "note": {
            "type": "string",
            "minLength": 1,
            "description": "e.g. \"Alerts never include amounts or client details beyond the name.\""
          }
        },
        "required": [
          "channel",
          "frequency"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named in message",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.me.alert_prefs",
  "service": "api notifications (new)",
  "local_work": "Resolve the record, check grants and authority, call api notifications (new); write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-CONVERSATION-NEW — Start a conversation

```json
{
  "id": "E-CONVERSATION-NEW",
  "title": "Start a conversation",
  "refs": [
    "R-ASSISTANT",
    "REC-CONVERSATION",
    "INV-ACCESS",
    "INV-AGENT",
    "D-CONVERSATION-MODEL",
    "T-ASSISTANT",
    "A-ASSISTANT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
  ],
  "method": "POST",
  "path": "/api/v1/assistant/conversations",
  "trigger": "Assistant page, choose Tola, Chidi or Zainab",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "Signed in; the agent must serve the person's role.",
  "parameters": [],
  "request": {
    "type": "object",
    "properties": {
      "agent": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "tola",
          "chidi",
          "zainab"
        ]
      }
    },
    "required": [
      "agent"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Start a conversation",
      "schema": {
        "type": "object",
        "properties": {
          "conversation_id": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "conversation_id"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named in message",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.assistant.new",
  "service": "agents (new)",
  "local_work": "Resolve the record, check grants and authority, call agents (new); write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-MESSAGE — Ask the assistant

```json
{
  "id": "E-MESSAGE",
  "title": "Ask the assistant",
  "refs": [
    "R-ASSISTANT",
    "REC-CONVERSATION",
    "REC-AGENTRUN",
    "INV-ACCESS",
    "INV-AGENT",
    "INV-SAMPLE",
    "D-CONVERSATION-MODEL",
    "D-AGENT-PROVIDER",
    "T-ASSISTANT",
    "A-ASSISTANT",
    "D-ASSISTANT-VIEW",
    "A-ASSISTANT-THREADS"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "POST",
  "path": "/api/v1/assistant/conversations/{conversation_id}/messages",
  "trigger": "Send a message",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "Own conversation; answers use only records the person may read.",
  "parameters": [
    {
      "name": "conversation_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": {
    "type": "object",
    "properties": {
      "text": {
        "type": "string",
        "minLength": 1,
        "description": "Up to 4000 characters"
      },
      "mentions": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "kind": {
              "type": "string",
              "minLength": 1,
              "enum": [
                "project",
                "work",
                "document",
                "person"
              ]
            },
            "id": {
              "type": "string",
              "minLength": 1
            }
          },
          "required": [
            "kind",
            "id"
          ],
          "additionalProperties": false
        }
      }
    },
    "required": [
      "text"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Ask the assistant",
      "schema": {
        "type": "object",
        "properties": {
          "message_id": {
            "type": "string",
            "minLength": 1
          },
          "agent_run_id": {
            "type": "string",
            "minLength": 1
          },
          "status": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "working",
              "answered",
              "cannot_answer"
            ]
          }
        },
        "required": [
          "message_id",
          "agent_run_id",
          "status"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named in message",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.assistant.message",
  "service": "agents coordinator",
  "local_work": "Resolve the record, check grants and authority, call agents coordinator; write one audit event.",
  "integration_calls": [
    {
      "integration": "I-AGENT",
      "operation": "run_assistant"
    }
  ],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-CONVERSATION — Read a conversation

```json
{
  "id": "E-CONVERSATION",
  "title": "Read a conversation",
  "refs": [
    "R-ASSISTANT",
    "REC-CONVERSATION",
    "REC-AGENTRUN",
    "INV-ACCESS",
    "INV-AGENT",
    "D-CONVERSATION-MODEL",
    "D-UPDATES",
    "T-ASSISTANT",
    "A-ASSISTANT",
    "D-ASSISTANT-VIEW",
    "A-ASSISTANT-THREADS"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "GET",
  "path": "/api/v1/assistant/conversations/{conversation_id}",
  "trigger": "Assistant page, polling while working",
  "security": [
    "Session"
  ],
  "permission": "Own conversation.",
  "parameters": [
    {
      "name": "conversation_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Read a conversation",
      "schema": {
        "type": "object",
        "properties": {
          "conversation_id": {
            "type": "string",
            "minLength": 1
          },
          "messages": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "role": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "person",
                    "agent"
                  ]
                },
                "text": {
                  "type": "string",
                  "minLength": 1
                },
                "steps": {
                  "type": "array",
                  "items": {
                    "type": "string",
                    "minLength": 1
                  }
                },
                "sources": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "kind": {
                        "type": "string",
                        "minLength": 1
                      },
                      "reference": {
                        "type": "string",
                        "minLength": 1
                      },
                      "restricted": {
                        "type": "boolean"
                      }
                    },
                    "required": [
                      "kind",
                      "reference",
                      "restricted"
                    ],
                    "additionalProperties": false
                  }
                },
                "draft_work_id": {
                  "type": "string"
                },
                "at": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date-time"
                },
                "step_details": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "text": {
                        "type": "string",
                        "minLength": 1
                      },
                      "state": {
                        "type": "string",
                        "minLength": 1,
                        "enum": [
                          "done",
                          "now",
                          "next"
                        ]
                      },
                      "reference": {
                        "type": "object",
                        "properties": {
                          "label": {
                            "type": "string",
                            "minLength": 1
                          },
                          "reference": {
                            "type": "string",
                            "minLength": 1
                          },
                          "work_id": {
                            "type": "string",
                            "minLength": 1
                          },
                          "document_id": {
                            "type": "string",
                            "minLength": 1
                          },
                          "case_id": {
                            "type": "string",
                            "minLength": 1
                          },
                          "evidence_id": {
                            "type": "string",
                            "minLength": 1
                          }
                        },
                        "required": [],
                        "additionalProperties": false
                      }
                    },
                    "required": [
                      "text",
                      "state"
                    ],
                    "additionalProperties": false
                  }
                },
                "handoff": {
                  "type": "object",
                  "properties": {
                    "from_agent": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "tola",
                        "chidi",
                        "zainab"
                      ]
                    },
                    "to": {
                      "type": "string",
                      "minLength": 1
                    },
                    "note": {
                      "type": "string",
                      "minLength": 1
                    }
                  },
                  "required": [
                    "note"
                  ],
                  "additionalProperties": false
                },
                "source_details": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "kind": {
                        "type": "string",
                        "minLength": 1
                      },
                      "label": {
                        "type": "string",
                        "minLength": 1
                      },
                      "reference": {
                        "type": "string",
                        "minLength": 1
                      },
                      "restricted": {
                        "type": "boolean"
                      },
                      "link": {
                        "type": "object",
                        "properties": {
                          "label": {
                            "type": "string",
                            "minLength": 1
                          },
                          "reference": {
                            "type": "string",
                            "minLength": 1
                          },
                          "work_id": {
                            "type": "string",
                            "minLength": 1
                          },
                          "document_id": {
                            "type": "string",
                            "minLength": 1
                          },
                          "case_id": {
                            "type": "string",
                            "minLength": 1
                          },
                          "evidence_id": {
                            "type": "string",
                            "minLength": 1
                          }
                        },
                        "required": [],
                        "additionalProperties": false
                      }
                    },
                    "required": [
                      "kind",
                      "label",
                      "restricted"
                    ],
                    "additionalProperties": false
                  }
                },
                "cannot_reason": {
                  "type": "string",
                  "minLength": 1
                },
                "draft": {
                  "type": "object",
                  "properties": {
                    "title": {
                      "type": "string",
                      "minLength": 1
                    },
                    "status_label": {
                      "type": "string",
                      "minLength": 1,
                      "description": "e.g. \"DRAFTED · NOT REVIEWED\""
                    },
                    "rows": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "label": {
                            "type": "string",
                            "minLength": 1
                          },
                          "value": {
                            "type": "string",
                            "minLength": 1
                          },
                          "money": {
                            "type": "object",
                            "properties": {
                              "amount": {
                                "type": "string",
                                "minLength": 1,
                                "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                                "description": "Decimal string; absent when unknown"
                              },
                              "currency": {
                                "type": "string",
                                "minLength": 1,
                                "pattern": "^[A-Z]{3}$"
                              },
                              "unknown": {
                                "type": "boolean"
                              }
                            },
                            "required": [
                              "currency",
                              "unknown"
                            ],
                            "additionalProperties": false,
                            "description": "Drafted amount. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                          }
                        },
                        "required": [
                          "label"
                        ],
                        "additionalProperties": false
                      }
                    },
                    "start": {
                      "type": "object",
                      "properties": {
                        "line_key": {
                          "type": "string",
                          "minLength": 1
                        },
                        "case_id": {
                          "type": "string",
                          "minLength": 1
                        },
                        "case_revision": {
                          "type": "integer",
                          "minimum": 1
                        },
                        "intake": {
                          "type": "object",
                          "additionalProperties": true,
                          "description": "Prefill for the line's E-LINES intake fields; the person reviews it in the normal Start work drawer"
                        },
                        "label": {
                          "type": "string",
                          "minLength": 1
                        }
                      },
                      "required": [
                        "line_key",
                        "label"
                      ],
                      "additionalProperties": false
                    },
                    "next": {
                      "type": "string",
                      "minLength": 1
                    },
                    "started": {
                      "type": "object",
                      "properties": {
                        "work_id": {
                          "type": "string",
                          "minLength": 1
                        },
                        "reference": {
                          "type": "string",
                          "minLength": 1
                        }
                      },
                      "required": [
                        "work_id"
                      ],
                      "additionalProperties": false
                    }
                  },
                  "required": [
                    "title",
                    "rows"
                  ],
                  "additionalProperties": false,
                  "description": "PROPOSAL (D-ASSISTANT-VIEW): a draft is started only through the normal E-WORK-START of its line (D-CONVERSATION-MODEL); started is present once it has been"
                }
              },
              "required": [
                "role",
                "text",
                "steps",
                "sources"
              ],
              "additionalProperties": false
            }
          },
          "agent": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "tola",
              "chidi",
              "zainab"
            ]
          },
          "title": {
            "type": "string",
            "minLength": 1
          },
          "status": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "working",
              "answered",
              "cannot_answer",
              "drafted"
            ]
          },
          "context": {
            "type": "object",
            "properties": {
              "project": {
                "type": "object",
                "properties": {
                  "case_id": {
                    "type": "string",
                    "minLength": 1
                  },
                  "title": {
                    "type": "string",
                    "minLength": 1
                  }
                },
                "required": [
                  "case_id",
                  "title"
                ],
                "additionalProperties": false
              },
              "access": {
                "type": "array",
                "items": {
                  "type": "string",
                  "minLength": 1,
                  "description": "\"Your access\" lines as the backend states them"
                }
              }
            },
            "required": [],
            "additionalProperties": false
          }
        },
        "required": [
          "conversation_id",
          "messages"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.assistant.read",
  "service": "agents (new)",
  "local_work": "Resolve the record, check grants and authority, call agents (new).",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-REPORT — Report with drill-down

```json
{
  "id": "E-REPORT",
  "title": "Report with drill-down",
  "refs": [
    "R-REPORTS",
    "REC-DOCUMENT",
    "REC-MONEY",
    "INV-ACCESS",
    "INV-UNKNOWN",
    "T-PROJECTS",
    "A-REPORT",
    "D-PROJECT-TAB-ROWS"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V5",
    "S-SCREENS"
  ],
  "method": "GET",
  "path": "/api/v1/reports/{report_id}",
  "trigger": "Leadership and project reports",
  "security": [
    "Session"
  ],
  "permission": "Report read; figures limited to visible records.",
  "parameters": [
    {
      "name": "report_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Report with drill-down",
      "schema": {
        "type": "object",
        "properties": {
          "report_id": {
            "type": "string",
            "minLength": 1
          },
          "title": {
            "type": "string",
            "minLength": 1
          },
          "figures": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "label": {
                  "type": "string",
                  "minLength": 1
                },
                "value": {
                  "type": "object",
                  "properties": {
                    "amount": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                      "description": "Decimal string; absent when unknown"
                    },
                    "currency": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^[A-Z]{3}$"
                    },
                    "unknown": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "currency",
                    "unknown"
                  ],
                  "additionalProperties": false
                },
                "sources": {
                  "type": "array",
                  "items": {
                    "type": "string",
                    "minLength": 1
                  }
                },
                "id": {
                  "type": "string",
                  "minLength": 1
                },
                "source_details": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "label": {
                        "type": "string",
                        "minLength": 1
                      },
                      "reference": {
                        "type": "string",
                        "minLength": 1
                      },
                      "kind": {
                        "type": "string",
                        "minLength": 1,
                        "enum": [
                          "document",
                          "rule",
                          "record",
                          "evidence"
                        ]
                      },
                      "document_id": {
                        "type": "string",
                        "minLength": 1
                      },
                      "work_id": {
                        "type": "string",
                        "minLength": 1
                      }
                    },
                    "required": [
                      "label",
                      "reference",
                      "kind"
                    ],
                    "additionalProperties": false
                  }
                }
              },
              "required": [
                "label",
                "value",
                "sources"
              ],
              "additionalProperties": false
            }
          },
          "agent": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "tola",
              "chidi",
              "zainab"
            ]
          }
        },
        "required": [
          "report_id",
          "title",
          "figures"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.reports.read",
  "service": "pmo reporting services",
  "local_work": "Resolve the record, check grants and authority, call pmo reporting services.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-LINE-OPTIONS — Options for a Start work field

```json
{
  "id": "E-LINE-OPTIONS",
  "title": "Options for a Start work field",
  "refs": [
    "R-START",
    "REC-CASE",
    "REC-GRANT",
    "INV-ACCESS",
    "INV-SAMPLE",
    "D-START-INTAKE",
    "D-PAGING",
    "T-START",
    "A-START-INTAKE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V5"
  ],
  "method": "GET",
  "path": "/api/v1/lines/{line_key}/fields/{field}/options",
  "trigger": "Open a record choice in a Start work drawer",
  "security": [
    "Session"
  ],
  "permission": "factory.start on the line; each option filtered by the person's grants.",
  "parameters": [
    {
      "name": "line_key",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "field",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "parent",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1,
        "description": "Value chosen in the field named by depends_on"
      }
    },
    {
      "name": "q",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "cursor",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "limit",
      "in": "query",
      "required": false,
      "schema": {
        "type": "integer",
        "enum": [
          10,
          20,
          50
        ],
        "description": "Rows per page chosen by the person; default 20"
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Options for a Start work field",
      "schema": {
        "type": "object",
        "properties": {
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "value": {
                  "type": "string",
                  "minLength": 1
                },
                "label": {
                  "type": "string",
                  "minLength": 1
                },
                "hint": {
                  "type": "string",
                  "minLength": 1
                },
                "case_id": {
                  "type": "string",
                  "minLength": 1
                },
                "case_revision": {
                  "type": "integer",
                  "minimum": 1
                },
                "disabled_reason": {
                  "type": "string",
                  "minLength": 1
                },
                "sample": {
                  "type": "boolean"
                }
              },
              "required": [
                "value",
                "label"
              ],
              "additionalProperties": false
            }
          },
          "next_cursor": {
            "type": "string"
          },
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          }
        },
        "required": [
          "items",
          "as_of"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.lines.options",
  "service": "workflows.factory_definitions + domain services",
  "local_work": "Resolve the record, check grants and authority, call workflows.factory_definitions + domain services.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-RFP-OUTCOME — Record an RFP outcome

```json
{
  "id": "E-RFP-OUTCOME",
  "title": "Record an RFP outcome",
  "refs": [
    "R-RESPONSE",
    "REC-WORK",
    "REC-EVIDENCE",
    "REC-AUDIT",
    "INV-ACCESS",
    "INV-REVISION",
    "INV-AUDIT",
    "INV-UNKNOWN",
    "D-RFP-OUTCOME",
    "T-RESPONSE",
    "A-RFP-OUTCOME",
    "A-WORKSPACE"
  ],
  "evidence": [
    "S-BACKEND",
    "S-DECISIONS-V5",
    "S-DECISIONS-V6",
    "S-SCREENS"
  ],
  "method": "POST",
  "path": "/api/v1/work/{work_id}/rfp-outcome",
  "trigger": "Record the outcome form (won, lost, pending, unknown)",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "rfp.outcome on the case, as the backend allows; lessons use rfp.dispose.",
  "parameters": [
    {
      "name": "work_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": {
    "type": "object",
    "properties": {
      "expected_revision": {
        "type": "integer",
        "minimum": 1
      },
      "case_revision": {
        "type": "integer",
        "minimum": 1
      },
      "submission_id": {
        "type": "string",
        "minLength": 1
      },
      "result": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "won",
          "lost",
          "pending",
          "unknown"
        ]
      },
      "learned_at": {
        "type": "string",
        "minLength": 1,
        "format": "date-time"
      },
      "record_as": {
        "type": "string",
        "minLength": 1,
        "description": "One of rfp_outcome.record_as[].value"
      },
      "evidence_id": {
        "type": "string",
        "minLength": 1
      },
      "note": {
        "type": "string",
        "description": "Up to 2000 characters"
      },
      "reason": {
        "type": "string",
        "minLength": 1,
        "description": "One of rfp_outcome.reasons[].value"
      },
      "lessons": {
        "type": "string",
        "description": "Lost: what we would do differently"
      },
      "awarded_amount": {
        "type": "object",
        "properties": {
          "amount": {
            "type": "string",
            "minLength": 1,
            "pattern": "^-?[0-9]+\\.[0-9]{2}$",
            "description": "Decimal string; absent when unknown"
          },
          "currency": {
            "type": "string",
            "minLength": 1,
            "pattern": "^[A-Z]{3}$"
          },
          "unknown": {
            "type": "boolean"
          }
        },
        "required": [
          "currency",
          "unknown"
        ],
        "additionalProperties": false,
        "description": "Won: as stated in the award letter. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
      },
      "expected_decision_on": {
        "type": "string",
        "minLength": 1,
        "format": "date"
      },
      "remind_at": {
        "type": "string",
        "minLength": 1,
        "format": "date-time"
      },
      "lessons_items": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "category": {
              "type": "string",
              "minLength": 1,
              "description": "One of rfp_outcome.lesson_categories[].value"
            },
            "text": {
              "type": "string",
              "minLength": 1
            }
          },
          "required": [
            "text"
          ],
          "additionalProperties": false
        }
      }
    },
    "required": [
      "expected_revision",
      "case_revision",
      "submission_id",
      "result",
      "learned_at",
      "record_as",
      "evidence_id"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Record an RFP outcome",
      "schema": {
        "type": "object",
        "properties": {
          "work_id": {
            "type": "string",
            "minLength": 1
          },
          "result": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "won",
              "lost",
              "pending",
              "unknown"
            ]
          },
          "state": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "ready",
              "processing",
              "waiting",
              "owner_needed",
              "setup_needed",
              "action_needed",
              "effect_uncertain",
              "awaiting_reconciliation",
              "verified",
              "cancelled",
              "followup_needed"
            ]
          },
          "revision": {
            "type": "integer",
            "minimum": 1
          },
          "engagement_work_id": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "work_id",
          "result",
          "state",
          "revision"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named in message",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.rfp.outcome",
  "service": "pmo.rfp.outcome / dispose",
  "local_work": "Resolve the record, check grants and authority, call pmo.rfp.outcome / dispose; write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-RFP-FOLLOWUP — Send the drafted RFP follow-up

```json
{
  "id": "E-RFP-FOLLOWUP",
  "title": "Send the drafted RFP follow-up",
  "refs": [
    "R-RESPONSE",
    "REC-WORK",
    "REC-EVIDENCE",
    "REC-AUDIT",
    "INV-ACCESS",
    "INV-REVISION",
    "INV-RESEND",
    "INV-AGENT",
    "INV-AUDIT",
    "D-RFP-OUTCOME",
    "T-RESPONSE",
    "A-RFP-FOLLOWUP"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "POST",
  "path": "/api/v1/work/{work_id}/rfp-outcome/followup",
  "trigger": "Send follow-up on the outcome-unknown board",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "rfp.outcome on the case, as the backend allows; agents rejected.",
  "parameters": [
    {
      "name": "work_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": {
    "type": "object",
    "properties": {
      "expected_revision": {
        "type": "integer",
        "minimum": 1
      },
      "version": {
        "type": "integer",
        "minimum": 1,
        "description": "rfp_outcome.followup.version being sent"
      },
      "body": {
        "type": "string",
        "minLength": 1,
        "description": "Edited text; absent sends the draft as is"
      },
      "idempotency_key": {
        "type": "string",
        "minLength": 1
      }
    },
    "required": [
      "expected_revision",
      "version",
      "idempotency_key"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Send the drafted RFP follow-up",
      "schema": {
        "type": "object",
        "properties": {
          "work_id": {
            "type": "string",
            "minLength": 1
          },
          "status": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "sending",
              "sent",
              "effect_uncertain"
            ]
          },
          "revision": {
            "type": "integer",
            "minimum": 1
          }
        },
        "required": [
          "work_id",
          "status",
          "revision"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named in message",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.rfp.followup",
  "service": "pmo.rfp (follow-up) + outbox",
  "local_work": "Resolve the record, check grants and authority, call pmo.rfp (follow-up) + outbox; write one audit event.",
  "integration_calls": [
    {
      "integration": "I-CLIENT-MESSAGES",
      "operation": "queue_client_message"
    }
  ],
  "failure_recovery": "Idempotent on idempotency_key. A send whose outcome is unknown returns effect_uncertain and blocks any resend until reconciled (INV-RESEND); 409 on a stale revision or draft version.",
  "implementation": "unimplemented"
}
```

### E-WORK-STEP — Take a line step

```json
{
  "id": "E-WORK-STEP",
  "title": "Take a line step",
  "refs": [
    "R-WORKITEM",
    "REC-WORK",
    "REC-EVIDENCE",
    "REC-AUDIT",
    "INV-ACCESS",
    "INV-REVISION",
    "INV-RESEND",
    "INV-AGENT",
    "INV-UNKNOWN",
    "INV-AUDIT",
    "D-LINE-WORKSPACE",
    "T-WORKSPACE",
    "A-WORKSPACE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "POST",
  "path": "/api/v1/work/{work_id}/steps",
  "trigger": "A step button in a line workspace (accept a suggestion, record impact, confirm minutes, send a reminder, etc.)",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "The step's authority on the line as the backend checks it; agents rejected for steps that approve, send or pay.",
  "parameters": [
    {
      "name": "work_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": {
    "type": "object",
    "properties": {
      "expected_revision": {
        "type": "integer",
        "minimum": 1
      },
      "step": {
        "type": "string",
        "minLength": 1,
        "description": "One of workspace.steps[].key"
      },
      "item_ids": {
        "type": "array",
        "items": {
          "type": "string",
          "minLength": 1
        }
      },
      "inputs": {
        "type": "object",
        "additionalProperties": true,
        "description": "Field name to value for the step's fields, shaped per field kind as in D-START-INTAKE"
      },
      "case_revision": {
        "type": "integer",
        "minimum": 1
      },
      "evidence_ids": {
        "type": "array",
        "items": {
          "type": "string",
          "minLength": 1
        }
      },
      "note": {
        "type": "string",
        "description": "Up to 2000 characters"
      },
      "idempotency_key": {
        "type": "string",
        "minLength": 1
      }
    },
    "required": [
      "expected_revision",
      "step",
      "idempotency_key"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Take a line step",
      "schema": {
        "type": "object",
        "properties": {
          "work_id": {
            "type": "string",
            "minLength": 1
          },
          "state": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "ready",
              "processing",
              "waiting",
              "owner_needed",
              "setup_needed",
              "action_needed",
              "effect_uncertain",
              "awaiting_reconciliation",
              "verified",
              "cancelled",
              "followup_needed"
            ]
          },
          "revision": {
            "type": "integer",
            "minimum": 1
          },
          "outcome": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "done",
              "queued",
              "effect_uncertain"
            ]
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "work_id",
          "state",
          "revision",
          "outcome"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          },
          "fields": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": {
                  "type": "string",
                  "minLength": 1
                },
                "message": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "name",
                "message"
              ],
              "additionalProperties": false
            }
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.work.step",
  "service": "workflows.factory (line step handlers)",
  "local_work": "Resolve the record, check grants and authority, call workflows.factory (line step handlers); write one audit event.",
  "integration_calls": [
    {
      "integration": "I-CLIENT-MESSAGES",
      "operation": "queue_client_message"
    }
  ],
  "failure_recovery": "Idempotent on idempotency_key. A step that sends and cannot confirm the send returns effect_uncertain; the work item then offers reconcile, never an automatic retry (INV-RESEND). 409 stale; 422 names fields.",
  "implementation": "unimplemented"
}
```

### E-WORK-ASSIGN — Assign the accountable person

```json
{
  "id": "E-WORK-ASSIGN",
  "title": "Assign the accountable person",
  "refs": [
    "R-START",
    "REC-WORK",
    "REC-GRANT",
    "REC-AUDIT",
    "INV-ACCESS",
    "INV-REVISION",
    "INV-AUDIT",
    "D-RFP-INTAKE",
    "T-ASSIGN",
    "A-ASSIGN"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "POST",
  "path": "/api/v1/work/{work_id}/assignment",
  "trigger": "Assign drawer from the Unassigned queue (SCR-24)",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "The assign authority configured for the line (e.g. rfp.assign).",
  "parameters": [
    {
      "name": "work_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": {
    "type": "object",
    "properties": {
      "expected_revision": {
        "type": "integer",
        "minimum": 1
      },
      "person_id": {
        "type": "string",
        "minLength": 1,
        "description": "One of assign.candidates[].person_id"
      },
      "note": {
        "type": "string",
        "description": "Up to 2000 characters"
      }
    },
    "required": [
      "expected_revision",
      "person_id"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Assign the accountable person",
      "schema": {
        "type": "object",
        "properties": {
          "work_id": {
            "type": "string",
            "minLength": 1
          },
          "state": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "ready",
              "processing",
              "waiting",
              "owner_needed",
              "setup_needed",
              "action_needed",
              "effect_uncertain",
              "awaiting_reconciliation",
              "verified",
              "cancelled",
              "followup_needed"
            ]
          },
          "revision": {
            "type": "integer",
            "minimum": 1
          },
          "assigned_to": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "work_id",
          "state",
          "revision",
          "assigned_to"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          },
          "fields": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": {
                  "type": "string",
                  "minLength": 1
                },
                "message": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "name",
                "message"
              ],
              "additionalProperties": false
            }
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.work.assign",
  "service": "pmo.rfp.assign",
  "local_work": "Resolve the record, check grants and authority, call pmo.rfp.assign; write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-ALERT-PREFS-READ — Read my alert preferences

```json
{
  "id": "E-ALERT-PREFS-READ",
  "title": "Read my alert preferences",
  "refs": [
    "R-ALERTS",
    "REC-ALERT-PREF",
    "INV-ACCESS",
    "D-NOTIFY-MODEL",
    "D-ALERT-PREFS-VIEW",
    "T-ALERTS",
    "A-ALERT-PREFS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "GET",
  "path": "/api/v1/me/alert-preferences",
  "trigger": "Alert settings page load",
  "security": [
    "Session"
  ],
  "permission": "Own preferences only.",
  "parameters": [],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Read my alert preferences",
      "schema": {
        "type": "object",
        "properties": {
          "channel": {
            "type": "string",
            "minLength": 1
          },
          "frequency": {
            "type": "string",
            "minLength": 1
          },
          "revision": {
            "type": "integer",
            "minimum": 1
          },
          "events": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "key": {
                  "type": "string",
                  "minLength": 1
                },
                "label": {
                  "type": "string",
                  "minLength": 1
                },
                "whatsapp": {
                  "type": "boolean"
                },
                "email": {
                  "type": "boolean"
                },
                "timing": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "immediate",
                    "daily_digest"
                  ]
                },
                "timing_label": {
                  "type": "string",
                  "minLength": 1
                },
                "locked_reason": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "key",
                "label",
                "whatsapp",
                "email"
              ],
              "additionalProperties": false
            }
          },
          "digest_at": {
            "type": "object",
            "properties": {
              "value": {
                "type": "string",
                "minLength": 1,
                "pattern": "^[0-2][0-9]:[0-5][0-9]$"
              },
              "options": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "value": {
                      "type": "string",
                      "minLength": 1
                    },
                    "label": {
                      "type": "string",
                      "minLength": 1
                    }
                  },
                  "required": [
                    "value",
                    "label"
                  ],
                  "additionalProperties": false
                }
              }
            },
            "required": [
              "options"
            ],
            "additionalProperties": false
          },
          "quiet_hours": {
            "type": "object",
            "properties": {
              "value": {
                "type": "string",
                "minLength": 1
              },
              "options": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "value": {
                      "type": "string",
                      "minLength": 1
                    },
                    "label": {
                      "type": "string",
                      "minLength": 1
                    }
                  },
                  "required": [
                    "value",
                    "label"
                  ],
                  "additionalProperties": false
                }
              }
            },
            "required": [
              "options"
            ],
            "additionalProperties": false
          },
          "whatsapp": {
            "type": "object",
            "properties": {
              "masked_number": {
                "type": "string",
                "minLength": 1,
                "description": "e.g. \"+234 803 *** 4412\"; never unmasked"
              },
              "verified": {
                "type": "boolean"
              }
            },
            "required": [
              "verified"
            ],
            "additionalProperties": false
          },
          "note": {
            "type": "string",
            "minLength": 1,
            "description": "e.g. \"Alerts never include amounts or client details beyond the name.\""
          }
        },
        "required": [
          "channel",
          "frequency",
          "revision",
          "events"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.me.alert_prefs_read",
  "service": "api notifications (new)",
  "local_work": "Resolve the record, check grants and authority, call api notifications (new).",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-NOTIFICATION-READ — Mark an alert read

```json
{
  "id": "E-NOTIFICATION-READ",
  "title": "Mark an alert read",
  "refs": [
    "R-ALERTS",
    "REC-NOTIFICATION",
    "REC-AUDIT",
    "INV-ACCESS",
    "INV-AUDIT",
    "D-NOTIFY-MODEL",
    "D-ALERT-PREFS-VIEW",
    "T-ALERTS",
    "A-NOTIFICATIONS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "POST",
  "path": "/api/v1/notifications/{notification_id}/read",
  "trigger": "Open an alert",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "Own notifications only.",
  "parameters": [
    {
      "name": "notification_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Mark an alert read",
      "schema": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string",
            "minLength": 1
          },
          "read": {
            "type": "boolean"
          },
          "unread_count": {
            "type": "integer",
            "minimum": 0
          }
        },
        "required": [
          "id",
          "read",
          "unread_count"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named in message",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.notifications.read",
  "service": "api notifications (new)",
  "local_work": "Resolve the record, check grants and authority, call api notifications (new); write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-CONVERSATIONS — My conversations

```json
{
  "id": "E-CONVERSATIONS",
  "title": "My conversations",
  "refs": [
    "R-ASSISTANT",
    "REC-CONVERSATION",
    "INV-ACCESS",
    "INV-AGENT",
    "D-CONVERSATION-MODEL",
    "D-ASSISTANT-VIEW",
    "D-PAGING",
    "T-ASSISTANT",
    "A-ASSISTANT-THREADS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "GET",
  "path": "/api/v1/assistant/conversations",
  "trigger": "Assistant page side list",
  "security": [
    "Session"
  ],
  "permission": "Own conversations only.",
  "parameters": [
    {
      "name": "cursor",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "limit",
      "in": "query",
      "required": false,
      "schema": {
        "type": "integer",
        "enum": [
          10,
          20,
          50
        ],
        "description": "Rows per page chosen by the person; default 20"
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "My conversations",
      "schema": {
        "type": "object",
        "properties": {
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "conversation_id": {
                  "type": "string",
                  "minLength": 1
                },
                "title": {
                  "type": "string",
                  "minLength": 1
                },
                "agent": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "tola",
                    "chidi",
                    "zainab"
                  ]
                },
                "status": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "working",
                    "answered",
                    "cannot_answer",
                    "drafted"
                  ]
                },
                "status_line": {
                  "type": "string",
                  "minLength": 1,
                  "description": "e.g. \"Working · step 3 of 5\", \"Can't share\""
                },
                "updated_at": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date-time"
                }
              },
              "required": [
                "conversation_id",
                "title",
                "agent",
                "status",
                "updated_at"
              ],
              "additionalProperties": false
            }
          },
          "next_cursor": {
            "type": "string"
          },
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          }
        },
        "required": [
          "items",
          "as_of"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.assistant.list",
  "service": "agents (new)",
  "local_work": "Resolve the record, check grants and authority, call agents (new).",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-MENTION-OPTIONS — Records I can mention

```json
{
  "id": "E-MENTION-OPTIONS",
  "title": "Records I can mention",
  "refs": [
    "R-ASSISTANT",
    "REC-CASE",
    "REC-WORK",
    "REC-DOCUMENT",
    "INV-ACCESS",
    "INV-RESTRICTED",
    "INV-SAMPLE",
    "D-ASSISTANT-VIEW",
    "D-PAGING",
    "T-ASSISTANT",
    "A-ASSISTANT-THREADS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "GET",
  "path": "/api/v1/assistant/mentions",
  "trigger": "Typing @ in the assistant composer",
  "security": [
    "Session"
  ],
  "permission": "Signed in; only records the person may read.",
  "parameters": [
    {
      "name": "q",
      "in": "query",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "kind",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "project",
          "work",
          "document",
          "person"
        ]
      }
    },
    {
      "name": "cursor",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "limit",
      "in": "query",
      "required": false,
      "schema": {
        "type": "integer",
        "enum": [
          10,
          20,
          50
        ],
        "description": "Rows per page chosen by the person; default 20"
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Records I can mention",
      "schema": {
        "type": "object",
        "properties": {
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "kind": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "project",
                    "work",
                    "document",
                    "person"
                  ]
                },
                "id": {
                  "type": "string",
                  "minLength": 1
                },
                "label": {
                  "type": "string",
                  "minLength": 1
                },
                "hint": {
                  "type": "string",
                  "minLength": 1
                },
                "sample": {
                  "type": "boolean"
                }
              },
              "required": [
                "kind",
                "id",
                "label"
              ],
              "additionalProperties": false
            }
          },
          "next_cursor": {
            "type": "string"
          },
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          }
        },
        "required": [
          "items",
          "as_of"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.assistant.mentions",
  "service": "identity.services.visible_cases + domain services",
  "local_work": "Resolve the record, check grants and authority, call identity.services.visible_cases + domain services.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-DELEGATIONS — Delegations I can see

```json
{
  "id": "E-DELEGATIONS",
  "title": "Delegations I can see",
  "refs": [
    "R-SETUP",
    "REC-CONFIG",
    "INV-ACCESS",
    "D-DELEGATION-VIEW",
    "D-PAGING",
    "T-SETUP",
    "A-DELEGATIONS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "GET",
  "path": "/api/v1/setup/delegations",
  "trigger": "Setup delegation tab",
  "security": [
    "Session"
  ],
  "permission": "Leads for their own authority; Admin as the backend allows.",
  "parameters": [
    {
      "name": "cursor",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "limit",
      "in": "query",
      "required": false,
      "schema": {
        "type": "integer",
        "enum": [
          10,
          20,
          50
        ],
        "description": "Rows per page chosen by the person; default 20"
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Delegations I can see",
      "schema": {
        "type": "object",
        "properties": {
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "delegation_id": {
                  "type": "string",
                  "minLength": 1
                },
                "from": {
                  "type": "object",
                  "properties": {
                    "name": {
                      "type": "string",
                      "minLength": 1
                    },
                    "role": {
                      "type": "string",
                      "minLength": 1
                    },
                    "is_you": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "name"
                  ],
                  "additionalProperties": false
                },
                "delegate": {
                  "type": "object",
                  "properties": {
                    "name": {
                      "type": "string",
                      "minLength": 1
                    },
                    "role": {
                      "type": "string",
                      "minLength": 1
                    },
                    "is_you": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "name"
                  ],
                  "additionalProperties": false
                },
                "authority": {
                  "type": "string",
                  "minLength": 1
                },
                "starts": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date"
                },
                "ends": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date"
                },
                "reason": {
                  "type": "string",
                  "minLength": 1
                },
                "status": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "scheduled",
                    "active",
                    "ended"
                  ]
                },
                "can_change": {
                  "type": "boolean"
                },
                "revision": {
                  "type": "integer",
                  "minimum": 1
                }
              },
              "required": [
                "delegation_id",
                "from",
                "delegate",
                "starts",
                "status"
              ],
              "additionalProperties": false
            }
          },
          "next_cursor": {
            "type": "string"
          },
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          },
          "authorities": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "value": {
                  "type": "string",
                  "minLength": 1
                },
                "label": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "value",
                "label"
              ],
              "additionalProperties": false
            }
          },
          "delegate_options": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "person_id": {
                  "type": "string",
                  "minLength": 1
                },
                "name": {
                  "type": "string",
                  "minLength": 1
                },
                "role": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "person_id",
                "name"
              ],
              "additionalProperties": false
            }
          },
          "revision": {
            "type": "integer",
            "minimum": 0
          }
        },
        "required": [
          "items",
          "as_of"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.setup.delegations",
  "service": "policy.role_assignments",
  "local_work": "Resolve the record, check grants and authority, call policy.role_assignments.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-PERSON-ROLES — Assign roles to a person

```json
{
  "id": "E-PERSON-ROLES",
  "title": "Assign roles to a person",
  "refs": [
    "R-SETUP",
    "REC-GRANT",
    "REC-AUDIT",
    "INV-ACCESS",
    "INV-REVISION",
    "INV-AUDIT",
    "D-PEOPLE-VIEW",
    "D-ADMIN-AUTHORITY",
    "T-SETUP-PEOPLE",
    "A-PEOPLE-ADMIN"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "PUT",
  "path": "/api/v1/setup/people/{person_id}/roles",
  "trigger": "Assign and resume held work (SCR-13 validation)",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "Role assignment authority as configured (D-ADMIN-AUTHORITY).",
  "parameters": [
    {
      "name": "person_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": {
    "type": "object",
    "properties": {
      "expected_revision": {
        "type": "integer",
        "minimum": 1
      },
      "roles": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "role": {
              "type": "string",
              "minLength": 1
            },
            "scope": {
              "type": "string",
              "minLength": 1
            }
          },
          "required": [
            "role"
          ],
          "additionalProperties": false
        }
      },
      "reason": {
        "type": "string",
        "minLength": 1
      },
      "resume_held": {
        "type": "boolean"
      }
    },
    "required": [
      "expected_revision",
      "roles"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Assign roles to a person",
      "schema": {
        "type": "object",
        "properties": {
          "person_id": {
            "type": "string",
            "minLength": 1
          },
          "revision": {
            "type": "integer",
            "minimum": 1
          },
          "resumed": {
            "type": "integer",
            "minimum": 0
          }
        },
        "required": [
          "person_id",
          "revision"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          },
          "fields": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": {
                  "type": "string",
                  "minLength": 1
                },
                "message": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "name",
                "message"
              ],
              "additionalProperties": false
            }
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.setup.person_roles",
  "service": "policy.role_assignments",
  "local_work": "Resolve the record, check grants and authority, call policy.role_assignments; write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-INVITE — Invite a staff member

```json
{
  "id": "E-INVITE",
  "title": "Invite a staff member",
  "refs": [
    "R-SETUP",
    "REC-GRANT",
    "REC-AUDIT",
    "INV-ACCESS",
    "INV-AUDIT",
    "D-PEOPLE-VIEW",
    "D-ADMIN-AUTHORITY",
    "D-SIGNIN",
    "T-SETUP-PEOPLE",
    "A-PEOPLE-ADMIN"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "POST",
  "path": "/api/v1/setup/people/invitations",
  "trigger": "Invite drawer (SCR-21 invite)",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "Account authority as configured (D-ADMIN-AUTHORITY).",
  "parameters": [],
  "request": {
    "type": "object",
    "properties": {
      "name": {
        "type": "string",
        "minLength": 1
      },
      "email": {
        "type": "string",
        "minLength": 1
      },
      "roles": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "role": {
              "type": "string",
              "minLength": 1
            },
            "scope": {
              "type": "string",
              "minLength": 1
            }
          },
          "required": [
            "role"
          ],
          "additionalProperties": false
        }
      },
      "idempotency_key": {
        "type": "string",
        "minLength": 1
      }
    },
    "required": [
      "name",
      "email",
      "roles",
      "idempotency_key"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Invite a staff member",
      "schema": {
        "type": "object",
        "properties": {
          "person_id": {
            "type": "string",
            "minLength": 1
          },
          "state": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "invited"
            ]
          }
        },
        "required": [
          "person_id",
          "state"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          },
          "fields": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": {
                  "type": "string",
                  "minLength": 1
                },
                "message": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "name",
                "message"
              ],
              "additionalProperties": false
            }
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.setup.invite",
  "service": "identity services",
  "local_work": "Resolve the record, check grants and authority, call identity services; write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-DEACTIVATE — Deactivate a staff account

```json
{
  "id": "E-DEACTIVATE",
  "title": "Deactivate a staff account",
  "refs": [
    "R-SETUP",
    "REC-GRANT",
    "REC-WORK",
    "REC-AUDIT",
    "INV-ACCESS",
    "INV-REVISION",
    "INV-AUDIT",
    "D-PEOPLE-VIEW",
    "D-ADMIN-AUTHORITY",
    "T-SETUP-PEOPLE",
    "A-PEOPLE-ADMIN"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "POST",
  "path": "/api/v1/setup/people/{person_id}/deactivation",
  "trigger": "Deactivate drawer with reassignment (SCR-21 deactivate)",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "Account authority as configured (D-ADMIN-AUTHORITY).",
  "parameters": [
    {
      "name": "person_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": {
    "type": "object",
    "properties": {
      "expected_revision": {
        "type": "integer",
        "minimum": 1
      },
      "reassign": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "work_id": {
              "type": "string",
              "minLength": 1
            },
            "person_id": {
              "type": "string",
              "minLength": 1
            }
          },
          "required": [
            "work_id",
            "person_id"
          ],
          "additionalProperties": false
        }
      },
      "reason": {
        "type": "string",
        "minLength": 1
      }
    },
    "required": [
      "expected_revision",
      "reason"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Deactivate a staff account",
      "schema": {
        "type": "object",
        "properties": {
          "person_id": {
            "type": "string",
            "minLength": 1
          },
          "state": {
            "type": "string",
            "minLength": 1,
            "enum": [
              "deactivated"
            ]
          },
          "reassigned": {
            "type": "integer",
            "minimum": 0
          },
          "revision": {
            "type": "integer",
            "minimum": 1
          }
        },
        "required": [
          "person_id",
          "state",
          "reassigned",
          "revision"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          },
          "fields": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": {
                  "type": "string",
                  "minLength": 1
                },
                "message": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "name",
                "message"
              ],
              "additionalProperties": false
            }
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.setup.deactivate",
  "service": "identity services + workflows reassignment",
  "local_work": "Resolve the record, check grants and authority, call identity services + workflows reassignment; write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-TEMPLATE-VERSION — Upload a new template version

```json
{
  "id": "E-TEMPLATE-VERSION",
  "title": "Upload a new template version",
  "refs": [
    "R-SETUP",
    "REC-DOCUMENT",
    "REC-AUDIT",
    "INV-ACCESS",
    "INV-REVISION",
    "INV-AUDIT",
    "INV-SAMPLE",
    "D-TEMPLATES-VIEW",
    "T-SETUP",
    "A-TEMPLATE-VERSION"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "POST",
  "path": "/api/v1/setup/templates/{template_id}/versions",
  "trigger": "Upload on Setup templates (SCR-34)",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "documents template authority as the backend allows.",
  "parameters": [
    {
      "name": "template_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": {
    "type": "object",
    "properties": {
      "expected_revision": {
        "type": "integer",
        "minimum": 1
      },
      "filename": {
        "type": "string",
        "minLength": 1
      },
      "content_base64": {
        "type": "string",
        "minLength": 1
      },
      "note": {
        "type": "string",
        "description": "Up to 2000 characters"
      }
    },
    "required": [
      "expected_revision",
      "filename",
      "content_base64"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Upload a new template version",
      "schema": {
        "type": "object",
        "properties": {
          "template_id": {
            "type": "string",
            "minLength": 1
          },
          "version": {
            "type": "string",
            "minLength": 1
          },
          "test_template": {
            "type": "boolean"
          },
          "revision": {
            "type": "integer",
            "minimum": 1
          }
        },
        "required": [
          "template_id",
          "version",
          "test_template",
          "revision"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          },
          "fields": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": {
                  "type": "string",
                  "minLength": 1
                },
                "message": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "name",
                "message"
              ],
              "additionalProperties": false
            }
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.setup.template_version",
  "service": "documents services",
  "local_work": "Resolve the record, check grants and authority, call documents services; write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

### E-COSTING-RULE — The costing rule and its versions

```json
{
  "id": "E-COSTING-RULE",
  "title": "The costing rule and its versions",
  "refs": [
    "R-SETUP",
    "REC-CONFIG",
    "INV-ACCESS",
    "INV-UNKNOWN",
    "D-SETUP-RULES-VIEW",
    "D-COSTING-RULE",
    "T-COSTING-RULE",
    "A-COSTING-RULE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "GET",
  "path": "/api/v1/setup/costing-rule",
  "trigger": "Setup costing rule tab (SCR-39)",
  "security": [
    "Session"
  ],
  "permission": "policy read for costing; Leads.",
  "parameters": [],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "The costing rule and its versions",
      "schema": {
        "type": "object",
        "properties": {
          "versions": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "version": {
                  "type": "integer",
                  "minimum": 1
                },
                "label": {
                  "type": "string",
                  "minLength": 1
                },
                "status": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "current",
                    "proposed",
                    "withdrawn",
                    "superseded"
                  ]
                },
                "proposed_by": {
                  "type": "object",
                  "properties": {
                    "name": {
                      "type": "string",
                      "minLength": 1
                    },
                    "role": {
                      "type": "string",
                      "minLength": 1
                    },
                    "is_you": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "name"
                  ],
                  "additionalProperties": false
                },
                "proposed_at": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date-time"
                },
                "reviewed_by": {
                  "type": "object",
                  "properties": {
                    "name": {
                      "type": "string",
                      "minLength": 1
                    },
                    "role": {
                      "type": "string",
                      "minLength": 1
                    },
                    "is_you": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "name"
                  ],
                  "additionalProperties": false
                },
                "effective_from": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date-time"
                }
              },
              "required": [
                "version",
                "label",
                "status"
              ],
              "additionalProperties": false
            }
          },
          "sections": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "key": {
                  "type": "string",
                  "minLength": 1
                },
                "kind": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "facts",
                    "table",
                    "checklist",
                    "findings",
                    "suggestions",
                    "recipients",
                    "figures",
                    "text",
                    "timeline"
                  ]
                },
                "title": {
                  "type": "string",
                  "minLength": 1
                },
                "note": {
                  "type": "string",
                  "minLength": 1
                },
                "agent": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "tola",
                    "chidi",
                    "zainab"
                  ]
                },
                "as_of": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date-time"
                },
                "coverage": {
                  "type": "string",
                  "minLength": 1
                },
                "restricted": {
                  "type": "boolean"
                },
                "restricted_label": {
                  "type": "string",
                  "minLength": 1
                },
                "columns": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "key": {
                        "type": "string",
                        "minLength": 1
                      },
                      "label": {
                        "type": "string",
                        "minLength": 1
                      },
                      "kind": {
                        "type": "string",
                        "minLength": 1,
                        "enum": [
                          "text",
                          "money",
                          "date",
                          "tag",
                          "reference",
                          "integer"
                        ]
                      }
                    },
                    "required": [
                      "key",
                      "label"
                    ],
                    "additionalProperties": false
                  }
                },
                "items": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "id": {
                        "type": "string",
                        "minLength": 1
                      },
                      "text": {
                        "type": "string",
                        "minLength": 1
                      },
                      "detail": {
                        "type": "string",
                        "minLength": 1
                      },
                      "label": {
                        "type": "string",
                        "minLength": 1
                      },
                      "value": {
                        "type": "string",
                        "minLength": 1
                      },
                      "money": {
                        "type": "object",
                        "properties": {
                          "amount": {
                            "type": "string",
                            "minLength": 1,
                            "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                            "description": "Decimal string; absent when unknown"
                          },
                          "currency": {
                            "type": "string",
                            "minLength": 1,
                            "pattern": "^[A-Z]{3}$"
                          },
                          "unknown": {
                            "type": "boolean"
                          }
                        },
                        "required": [
                          "currency",
                          "unknown"
                        ],
                        "additionalProperties": false,
                        "description": "Item amount. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                      },
                      "cells": {
                        "type": "array",
                        "items": {
                          "type": "object",
                          "properties": {
                            "column": {
                              "type": "string",
                              "minLength": 1
                            },
                            "text": {
                              "type": "string",
                              "minLength": 1
                            },
                            "money": {
                              "type": "object",
                              "properties": {
                                "amount": {
                                  "type": "string",
                                  "minLength": 1,
                                  "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                                  "description": "Decimal string; absent when unknown"
                                },
                                "currency": {
                                  "type": "string",
                                  "minLength": 1,
                                  "pattern": "^[A-Z]{3}$"
                                },
                                "unknown": {
                                  "type": "boolean"
                                }
                              },
                              "required": [
                                "currency",
                                "unknown"
                              ],
                              "additionalProperties": false,
                              "description": "Cell amount. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                            },
                            "date": {
                              "type": "object",
                              "properties": {
                                "date": {
                                  "type": "string",
                                  "minLength": 1,
                                  "format": "date"
                                },
                                "unknown": {
                                  "type": "boolean"
                                }
                              },
                              "required": [
                                "unknown"
                              ],
                              "additionalProperties": false
                            },
                            "tag": {
                              "type": "object",
                              "properties": {
                                "label": {
                                  "type": "string",
                                  "minLength": 1
                                },
                                "tone": {
                                  "type": "string",
                                  "minLength": 1,
                                  "enum": [
                                    "neutral",
                                    "person",
                                    "agent",
                                    "stopped",
                                    "uncertain",
                                    "verified",
                                    "restricted"
                                  ],
                                  "description": "Display tone the backend assigns; the frontend maps it to the design-system tag colour and never derives it from state names"
                                }
                              },
                              "required": [
                                "label"
                              ],
                              "additionalProperties": false
                            },
                            "link": {
                              "type": "object",
                              "properties": {
                                "label": {
                                  "type": "string",
                                  "minLength": 1
                                },
                                "reference": {
                                  "type": "string",
                                  "minLength": 1
                                },
                                "work_id": {
                                  "type": "string",
                                  "minLength": 1
                                },
                                "document_id": {
                                  "type": "string",
                                  "minLength": 1
                                },
                                "case_id": {
                                  "type": "string",
                                  "minLength": 1
                                },
                                "evidence_id": {
                                  "type": "string",
                                  "minLength": 1
                                }
                              },
                              "required": [],
                              "additionalProperties": false
                            },
                            "restricted": {
                              "type": "boolean"
                            }
                          },
                          "required": [
                            "column"
                          ],
                          "additionalProperties": false
                        }
                      },
                      "status": {
                        "type": "string",
                        "minLength": 1,
                        "enum": [
                          "done",
                          "now",
                          "next",
                          "not_yet",
                          "held",
                          "blocked",
                          "unknown",
                          "not_applicable"
                        ]
                      },
                      "tag": {
                        "type": "object",
                        "properties": {
                          "label": {
                            "type": "string",
                            "minLength": 1
                          },
                          "tone": {
                            "type": "string",
                            "minLength": 1,
                            "enum": [
                              "neutral",
                              "person",
                              "agent",
                              "stopped",
                              "uncertain",
                              "verified",
                              "restricted"
                            ],
                            "description": "Display tone the backend assigns; the frontend maps it to the design-system tag colour and never derives it from state names"
                          }
                        },
                        "required": [
                          "label"
                        ],
                        "additionalProperties": false
                      },
                      "severity": {
                        "type": "string",
                        "minLength": 1,
                        "enum": [
                          "high",
                          "medium",
                          "low",
                          "info"
                        ]
                      },
                      "owner": {
                        "type": "object",
                        "properties": {
                          "name": {
                            "type": "string",
                            "minLength": 1
                          },
                          "role": {
                            "type": "string",
                            "minLength": 1
                          },
                          "recorded_by_pm": {
                            "type": "boolean"
                          },
                          "outside_party": {
                            "type": "boolean"
                          }
                        },
                        "required": [
                          "name"
                        ],
                        "additionalProperties": false
                      },
                      "due": {
                        "type": "object",
                        "properties": {
                          "date": {
                            "type": "string",
                            "minLength": 1,
                            "format": "date"
                          },
                          "unknown": {
                            "type": "boolean"
                          }
                        },
                        "required": [
                          "unknown"
                        ],
                        "additionalProperties": false
                      },
                      "held_by": {
                        "type": "object",
                        "properties": {
                          "kind": {
                            "type": "string",
                            "minLength": 1,
                            "enum": [
                              "person",
                              "role",
                              "agent",
                              "outside_party",
                              "factory"
                            ]
                          },
                          "name": {
                            "type": "string",
                            "minLength": 1,
                            "description": "Person, role, agent or outside party name as recorded"
                          },
                          "is_you": {
                            "type": "boolean"
                          }
                        },
                        "required": [
                          "kind",
                          "name",
                          "is_you"
                        ],
                        "additionalProperties": false
                      },
                      "agent": {
                        "type": "string",
                        "minLength": 1,
                        "enum": [
                          "tola",
                          "chidi",
                          "zainab"
                        ]
                      },
                      "at": {
                        "type": "string",
                        "minLength": 1,
                        "format": "date-time"
                      },
                      "cites": {
                        "type": "array",
                        "items": {
                          "type": "object",
                          "properties": {
                            "label": {
                              "type": "string",
                              "minLength": 1
                            },
                            "reference": {
                              "type": "string",
                              "minLength": 1
                            },
                            "work_id": {
                              "type": "string",
                              "minLength": 1
                            },
                            "document_id": {
                              "type": "string",
                              "minLength": 1
                            },
                            "case_id": {
                              "type": "string",
                              "minLength": 1
                            },
                            "evidence_id": {
                              "type": "string",
                              "minLength": 1
                            }
                          },
                          "required": [],
                          "additionalProperties": false
                        }
                      },
                      "cite_label": {
                        "type": "string",
                        "minLength": 1,
                        "description": "e.g. \"2 RECORDS\""
                      },
                      "channel": {
                        "type": "string",
                        "minLength": 1
                      },
                      "receipt": {
                        "type": "string",
                        "minLength": 1,
                        "enum": [
                          "received",
                          "not_yet",
                          "uncertain",
                          "failed",
                          "unknown"
                        ]
                      },
                      "restricted": {
                        "type": "boolean"
                      },
                      "steps": {
                        "type": "array",
                        "items": {
                          "type": "string",
                          "minLength": 1,
                          "description": "Keys of workspace.steps that act on this item"
                        }
                      }
                    },
                    "required": [
                      "id"
                    ],
                    "additionalProperties": false
                  }
                },
                "total": {
                  "type": "integer",
                  "minimum": 0
                },
                "filters": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "value": {
                        "type": "string",
                        "minLength": 1
                      },
                      "label": {
                        "type": "string",
                        "minLength": 1
                      }
                    },
                    "required": [
                      "value",
                      "label"
                    ],
                    "additionalProperties": false
                  }
                },
                "next_cursor": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "key",
                "kind",
                "items"
              ],
              "additionalProperties": false
            }
          },
          "examples": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "label": {
                  "type": "string",
                  "minLength": 1
                },
                "expected": {
                  "type": "object",
                  "properties": {
                    "amount": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                      "description": "Decimal string; absent when unknown"
                    },
                    "currency": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^[A-Z]{3}$"
                    },
                    "unknown": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "currency",
                    "unknown"
                  ],
                  "additionalProperties": false,
                  "description": "Expected result. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                },
                "computed": {
                  "type": "object",
                  "properties": {
                    "amount": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                      "description": "Decimal string; absent when unknown"
                    },
                    "currency": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^[A-Z]{3}$"
                    },
                    "unknown": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "currency",
                    "unknown"
                  ],
                  "additionalProperties": false,
                  "description": "Result under the version. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                },
                "result": {
                  "type": "string",
                  "minLength": 1,
                  "enum": [
                    "match",
                    "differs",
                    "unknown"
                  ]
                }
              },
              "required": [
                "label",
                "result"
              ],
              "additionalProperties": false
            }
          },
          "review_work_id": {
            "type": "string",
            "minLength": 1
          },
          "cannot_review_reason": {
            "type": "string",
            "minLength": 1,
            "description": "e.g. \"you proposed this version\""
          },
          "not_set": {
            "type": "boolean"
          }
        },
        "required": [
          "versions",
          "not_set"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.setup.costing_rule",
  "service": "policy.services.resolve (costing)",
  "local_work": "Resolve the record, check grants and authority, call policy.services.resolve (costing).",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-INVOICES — Invoices and what is owed

```json
{
  "id": "E-INVOICES",
  "title": "Invoices and what is owed",
  "refs": [
    "R-FINANCE",
    "REC-MONEY",
    "INV-ACCESS",
    "INV-UNKNOWN",
    "INV-FACTS",
    "INV-SAMPLE",
    "D-RECEIVABLES-VIEW",
    "D-PAGING",
    "T-RECEIVABLES",
    "A-RECEIVABLES"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "GET",
  "path": "/api/v1/finance/invoices",
  "trigger": "Payments and follow-up (SCR-20)",
  "security": [
    "Session"
  ],
  "permission": "finance.read; rows filtered by grants.",
  "parameters": [
    {
      "name": "q",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "status",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1,
        "description": "One of filters[].value as the backend lists them"
      }
    },
    {
      "name": "client",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "cursor",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "limit",
      "in": "query",
      "required": false,
      "schema": {
        "type": "integer",
        "enum": [
          10,
          20,
          50
        ],
        "description": "Rows per page chosen by the person; default 20"
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Invoices and what is owed",
      "schema": {
        "type": "object",
        "properties": {
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "invoice_id": {
                  "type": "string",
                  "minLength": 1
                },
                "reference": {
                  "type": "string",
                  "minLength": 1
                },
                "client": {
                  "type": "string",
                  "minLength": 1
                },
                "project": {
                  "type": "object",
                  "properties": {
                    "case_id": {
                      "type": "string",
                      "minLength": 1
                    },
                    "title": {
                      "type": "string",
                      "minLength": 1
                    }
                  },
                  "required": [
                    "case_id",
                    "title"
                  ],
                  "additionalProperties": false
                },
                "issued_on": {
                  "type": "string",
                  "minLength": 1,
                  "format": "date"
                },
                "due": {
                  "type": "object",
                  "properties": {
                    "date": {
                      "type": "string",
                      "minLength": 1,
                      "format": "date"
                    },
                    "unknown": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "unknown"
                  ],
                  "additionalProperties": false
                },
                "invoiced": {
                  "type": "object",
                  "properties": {
                    "amount": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                      "description": "Decimal string; absent when unknown"
                    },
                    "currency": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^[A-Z]{3}$"
                    },
                    "unknown": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "currency",
                    "unknown"
                  ],
                  "additionalProperties": false,
                  "description": "Invoiced amount. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                },
                "received": {
                  "type": "object",
                  "properties": {
                    "amount": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                      "description": "Decimal string; absent when unknown"
                    },
                    "currency": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^[A-Z]{3}$"
                    },
                    "unknown": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "currency",
                    "unknown"
                  ],
                  "additionalProperties": false,
                  "description": "Receipts recorded by Finance. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                },
                "owed": {
                  "type": "object",
                  "properties": {
                    "amount": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                      "description": "Decimal string; absent when unknown"
                    },
                    "currency": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^[A-Z]{3}$"
                    },
                    "unknown": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "currency",
                    "unknown"
                  ],
                  "additionalProperties": false,
                  "description": "Still owed, as composed by the backend. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                },
                "status": {
                  "type": "object",
                  "properties": {
                    "label": {
                      "type": "string",
                      "minLength": 1
                    },
                    "tone": {
                      "type": "string",
                      "minLength": 1,
                      "enum": [
                        "neutral",
                        "person",
                        "agent",
                        "stopped",
                        "uncertain",
                        "verified",
                        "restricted"
                      ],
                      "description": "Display tone the backend assigns; the frontend maps it to the design-system tag colour and never derives it from state names"
                    }
                  },
                  "required": [
                    "label"
                  ],
                  "additionalProperties": false
                },
                "work_id": {
                  "type": "string",
                  "minLength": 1
                },
                "revision": {
                  "type": "integer",
                  "minimum": 1
                },
                "reminder": {
                  "type": "object",
                  "properties": {
                    "status": {
                      "type": "string",
                      "minLength": 1
                    },
                    "last_sent_at": {
                      "type": "string",
                      "minLength": 1,
                      "format": "date-time"
                    },
                    "work_id": {
                      "type": "string",
                      "minLength": 1
                    }
                  },
                  "required": [
                    "status"
                  ],
                  "additionalProperties": false
                },
                "sample": {
                  "type": "boolean"
                }
              },
              "required": [
                "invoice_id",
                "reference",
                "invoiced",
                "received",
                "owed"
              ],
              "additionalProperties": false
            }
          },
          "next_cursor": {
            "type": "string"
          },
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          },
          "totals": {
            "type": "object",
            "properties": {
              "invoiced": {
                "type": "object",
                "properties": {
                  "amount": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                    "description": "Decimal string; absent when unknown"
                  },
                  "currency": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": "^[A-Z]{3}$"
                  },
                  "unknown": {
                    "type": "boolean"
                  }
                },
                "required": [
                  "currency",
                  "unknown"
                ],
                "additionalProperties": false,
                "description": "Total invoiced. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
              },
              "received": {
                "type": "object",
                "properties": {
                  "amount": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                    "description": "Decimal string; absent when unknown"
                  },
                  "currency": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": "^[A-Z]{3}$"
                  },
                  "unknown": {
                    "type": "boolean"
                  }
                },
                "required": [
                  "currency",
                  "unknown"
                ],
                "additionalProperties": false,
                "description": "Total received. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
              },
              "owed": {
                "type": "object",
                "properties": {
                  "amount": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                    "description": "Decimal string; absent when unknown"
                  },
                  "currency": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": "^[A-Z]{3}$"
                  },
                  "unknown": {
                    "type": "boolean"
                  }
                },
                "required": [
                  "currency",
                  "unknown"
                ],
                "additionalProperties": false,
                "description": "Total owed. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
              }
            },
            "required": [],
            "additionalProperties": false
          },
          "filters": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "value": {
                  "type": "string",
                  "minLength": 1
                },
                "label": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "value",
                "label"
              ],
              "additionalProperties": false
            }
          },
          "total": {
            "type": "integer",
            "minimum": 0
          }
        },
        "required": [
          "items",
          "as_of"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.finance.invoices",
  "service": "finance services",
  "local_work": "Resolve the record, check grants and authority, call finance services.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-RECEIPT — Record a receipt

```json
{
  "id": "E-RECEIPT",
  "title": "Record a receipt",
  "refs": [
    "R-FINANCE",
    "REC-MONEY",
    "REC-EVIDENCE",
    "REC-AUDIT",
    "INV-ACCESS",
    "INV-REVISION",
    "INV-FACTS",
    "INV-UNKNOWN",
    "INV-AGENT",
    "INV-AUDIT",
    "D-RECEIVABLES-VIEW",
    "D-RECEIPT-ALLOCATION",
    "T-RECEIVABLES",
    "A-RECEIVABLES"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "POST",
  "path": "/api/v1/finance/invoices/{invoice_id}/receipts",
  "trigger": "Record a payment (SCR-20 record)",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "finance receipt authority as configured; agents rejected.",
  "parameters": [
    {
      "name": "invoice_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": {
    "type": "object",
    "properties": {
      "expected_revision": {
        "type": "integer",
        "minimum": 1
      },
      "amount": {
        "type": "object",
        "properties": {
          "amount": {
            "type": "string",
            "minLength": 1,
            "pattern": "^-?[0-9]+\\.[0-9]{2}$",
            "description": "Decimal string; absent when unknown"
          },
          "currency": {
            "type": "string",
            "minLength": 1,
            "pattern": "^[A-Z]{3}$"
          },
          "unknown": {
            "type": "boolean"
          }
        },
        "required": [
          "currency",
          "unknown"
        ],
        "additionalProperties": false,
        "description": "Amount as on the bank record; must be known to record"
      },
      "received_on": {
        "type": "string",
        "minLength": 1,
        "format": "date"
      },
      "bank_reference": {
        "type": "string",
        "minLength": 1
      },
      "evidence_id": {
        "type": "string",
        "minLength": 1
      },
      "case_revision": {
        "type": "integer",
        "minimum": 1
      },
      "idempotency_key": {
        "type": "string",
        "minLength": 1
      }
    },
    "required": [
      "expected_revision",
      "amount",
      "received_on",
      "evidence_id",
      "idempotency_key"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Record a receipt",
      "schema": {
        "type": "object",
        "properties": {
          "receipt_id": {
            "type": "string",
            "minLength": 1
          },
          "invoice_id": {
            "type": "string",
            "minLength": 1
          },
          "revision": {
            "type": "integer",
            "minimum": 1
          },
          "allocation": {
            "type": "object",
            "properties": {
              "label": {
                "type": "string",
                "minLength": 1
              },
              "tone": {
                "type": "string",
                "minLength": 1,
                "enum": [
                  "neutral",
                  "person",
                  "agent",
                  "stopped",
                  "uncertain",
                  "verified",
                  "restricted"
                ],
                "description": "Display tone the backend assigns; the frontend maps it to the design-system tag colour and never derives it from state names"
              }
            },
            "required": [
              "label"
            ],
            "additionalProperties": false
          }
        },
        "required": [
          "receipt_id",
          "invoice_id",
          "revision"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          },
          "fields": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": {
                  "type": "string",
                  "minLength": 1
                },
                "message": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "name",
                "message"
              ],
              "additionalProperties": false
            }
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.finance.receipt",
  "service": "finance services (receipts; allocation per D-RECEIPT-ALLOCATION)",
  "local_work": "Resolve the record, check grants and authority, call finance services (receipts; allocation per D-RECEIPT-ALLOCATION); write one audit event.",
  "integration_calls": [],
  "failure_recovery": "Idempotent on idempotency_key; a retried request never records a second receipt. 409 stale; 422 names fields. Allocation is composed by the backend and returned, never by the frontend.",
  "implementation": "unimplemented"
}
```

### E-CLIENTS — Clients

```json
{
  "id": "E-CLIENTS",
  "title": "Clients",
  "refs": [
    "R-PROJECT",
    "REC-CLIENT",
    "INV-ACCESS",
    "INV-UNKNOWN",
    "INV-SAMPLE",
    "D-CLIENTS-VIEW",
    "D-PAGING",
    "T-CLIENTS",
    "A-CLIENTS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "GET",
  "path": "/api/v1/clients",
  "trigger": "Clients page (SCR-35)",
  "security": [
    "Session"
  ],
  "permission": "case.read on at least one of the client's cases.",
  "parameters": [
    {
      "name": "q",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "cursor",
      "in": "query",
      "required": false,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    },
    {
      "name": "limit",
      "in": "query",
      "required": false,
      "schema": {
        "type": "integer",
        "enum": [
          10,
          20,
          50
        ],
        "description": "Rows per page chosen by the person; default 20"
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Clients",
      "schema": {
        "type": "object",
        "properties": {
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "client_id": {
                  "type": "string",
                  "minLength": 1
                },
                "name": {
                  "type": "string",
                  "minLength": 1
                },
                "projects": {
                  "type": "integer",
                  "minimum": 0
                },
                "owed": {
                  "type": "object",
                  "properties": {
                    "amount": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                      "description": "Decimal string; absent when unknown"
                    },
                    "currency": {
                      "type": "string",
                      "minLength": 1,
                      "pattern": "^[A-Z]{3}$"
                    },
                    "unknown": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "currency",
                    "unknown"
                  ],
                  "additionalProperties": false,
                  "description": "Owed across visible invoices. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
                },
                "billing_contact_set": {
                  "type": "boolean"
                },
                "sample": {
                  "type": "boolean"
                }
              },
              "required": [
                "client_id",
                "name",
                "billing_contact_set"
              ],
              "additionalProperties": false
            }
          },
          "next_cursor": {
            "type": "string"
          },
          "as_of": {
            "type": "string",
            "minLength": 1,
            "format": "date-time"
          }
        },
        "required": [
          "items",
          "as_of"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.clients.list",
  "service": "pmo client register",
  "local_work": "Resolve the record, check grants and authority, call pmo client register.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-CLIENT — Client detail

```json
{
  "id": "E-CLIENT",
  "title": "Client detail",
  "refs": [
    "R-PROJECT",
    "REC-CLIENT",
    "REC-CASE",
    "REC-MONEY",
    "INV-ACCESS",
    "INV-UNKNOWN",
    "INV-FACTS",
    "D-CLIENTS-VIEW",
    "T-CLIENTS",
    "A-CLIENTS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "GET",
  "path": "/api/v1/clients/{client_id}",
  "trigger": "Open a client (SCR-35 detail)",
  "security": [
    "Session"
  ],
  "permission": "As E-CLIENTS.",
  "parameters": [
    {
      "name": "client_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": null,
  "responses": [
    {
      "status": "200",
      "description": "Client detail",
      "schema": {
        "type": "object",
        "properties": {
          "client_id": {
            "type": "string",
            "minLength": 1
          },
          "name": {
            "type": "string",
            "minLength": 1
          },
          "revision": {
            "type": "integer",
            "minimum": 1
          },
          "billing_contact": {
            "type": "object",
            "properties": {
              "name": {
                "type": "string",
                "minLength": 1
              },
              "email": {
                "type": "string",
                "minLength": 1
              },
              "set": {
                "type": "boolean"
              }
            },
            "required": [
              "set"
            ],
            "additionalProperties": false
          },
          "projects": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "case_id": {
                  "type": "string",
                  "minLength": 1
                },
                "title": {
                  "type": "string",
                  "minLength": 1
                },
                "stage": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "case_id",
                "title"
              ],
              "additionalProperties": false
            }
          },
          "money": {
            "type": "object",
            "properties": {
              "invoiced": {
                "type": "object",
                "properties": {
                  "amount": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                    "description": "Decimal string; absent when unknown"
                  },
                  "currency": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": "^[A-Z]{3}$"
                  },
                  "unknown": {
                    "type": "boolean"
                  }
                },
                "required": [
                  "currency",
                  "unknown"
                ],
                "additionalProperties": false,
                "description": "Invoiced. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
              },
              "received": {
                "type": "object",
                "properties": {
                  "amount": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                    "description": "Decimal string; absent when unknown"
                  },
                  "currency": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": "^[A-Z]{3}$"
                  },
                  "unknown": {
                    "type": "boolean"
                  }
                },
                "required": [
                  "currency",
                  "unknown"
                ],
                "additionalProperties": false,
                "description": "Received. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
              },
              "owed": {
                "type": "object",
                "properties": {
                  "amount": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": "^-?[0-9]+\\.[0-9]{2}$",
                    "description": "Decimal string; absent when unknown"
                  },
                  "currency": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": "^[A-Z]{3}$"
                  },
                  "unknown": {
                    "type": "boolean"
                  }
                },
                "required": [
                  "currency",
                  "unknown"
                ],
                "additionalProperties": false,
                "description": "Owed. When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN)."
              }
            },
            "required": [],
            "additionalProperties": false
          },
          "blocked": {
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1,
              "description": "e.g. \"Invoices wait until a billing contact is set\""
            }
          },
          "can_change": {
            "type": "boolean"
          },
          "sample": {
            "type": "boolean"
          }
        },
        "required": [
          "client_id",
          "name",
          "revision",
          "billing_contact",
          "projects"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.clients.read",
  "service": "pmo client register",
  "local_work": "Resolve the record, check grants and authority, call pmo client register.",
  "integration_calls": [],
  "failure_recovery": "Read-only; 404 hides records the person may not see.",
  "implementation": "unimplemented"
}
```

### E-CLIENT-CONTACT — Set the billing contact

```json
{
  "id": "E-CLIENT-CONTACT",
  "title": "Set the billing contact",
  "refs": [
    "R-PROJECT",
    "REC-CLIENT",
    "REC-AUDIT",
    "INV-ACCESS",
    "INV-REVISION",
    "INV-AUDIT",
    "D-CLIENTS-VIEW",
    "T-CLIENTS",
    "A-CLIENTS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND",
    "S-DECISIONS-V6"
  ],
  "method": "PUT",
  "path": "/api/v1/clients/{client_id}/billing-contact",
  "trigger": "Billing contact form (SCR-35 detail)",
  "security": [
    "Session",
    "Csrf"
  ],
  "permission": "client contact authority as the backend allows.",
  "parameters": [
    {
      "name": "client_id",
      "in": "path",
      "required": true,
      "schema": {
        "type": "string",
        "minLength": 1
      }
    }
  ],
  "request": {
    "type": "object",
    "properties": {
      "expected_revision": {
        "type": "integer",
        "minimum": 1
      },
      "name": {
        "type": "string",
        "minLength": 1
      },
      "email": {
        "type": "string",
        "minLength": 1
      },
      "reason": {
        "type": "string",
        "minLength": 1
      }
    },
    "required": [
      "expected_revision",
      "name",
      "email"
    ],
    "additionalProperties": false
  },
  "responses": [
    {
      "status": "200",
      "description": "Set the billing contact",
      "schema": {
        "type": "object",
        "properties": {
          "client_id": {
            "type": "string",
            "minLength": 1
          },
          "revision": {
            "type": "integer",
            "minimum": 1
          }
        },
        "required": [
          "client_id",
          "revision"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "401",
      "description": "Not signed in",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "403",
      "description": "No grant for this record",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "404",
      "description": "Not found or not visible",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "409",
      "description": "Stale revision: the record changed; reload and act on the current version",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    },
    {
      "status": "422",
      "description": "Validation failed; fields named",
      "schema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "minLength": 1
          },
          "message": {
            "type": "string",
            "minLength": 1
          },
          "fields": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": {
                  "type": "string",
                  "minLength": 1
                },
                "message": {
                  "type": "string",
                  "minLength": 1
                }
              },
              "required": [
                "name",
                "message"
              ],
              "additionalProperties": false
            }
          }
        },
        "required": [
          "code",
          "message"
        ],
        "additionalProperties": false
      }
    }
  ],
  "handler": "api.clients.contact",
  "service": "pmo client register",
  "local_work": "Resolve the record, check grants and authority, call pmo client register; write one audit event.",
  "integration_calls": [],
  "failure_recovery": "409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.",
  "implementation": "unimplemented"
}
```

## Decisions and client inputs

- D-API-STYLE r2 (proposed, owner: backend developer): Plain Django JSON views under /api/v1 in a new apps/api package that call the existing service functions; no new framework. — Unchanged choice; the decision now belongs to the backend developer. The frontend builds against it as a working assumption (design engineer, 13 Nov 2026).

- D-AUTH r2 (proposed, owner: backend developer): Same-origin deployment: the Next.js app and /api/v1 are served behind one host; the Django session cookie authenticates; writes send the CSRF token header. — Unchanged choice; the decision now belongs to the backend developer. The frontend builds against it as a working assumption (design engineer, 13 Nov 2026).

- D-HOSTING r1 (open, owner: release authority): Not chosen. Needed before the first release, not before local development. — No deployment is authorised in this phase.

- D-UPDATES r2 (approved, owner: technical reviewer): Polling: lists every 15 seconds while visible, an open work item every 5 seconds while an agent is working; no push channel in v1. — Accepted as proposed by the design engineer, 13 Nov 2026 (frontend behaviour).

- D-PAGING r2 (approved, owner: technical reviewer): Cursor paging with a rows-per-page choice of 10, 20 or 50 on every list (default 20); newest activity first; counts per queue returned separately. — Design engineer, 13 Nov 2026: users choose 10, 20 or 50 rows per page. Default 20 is a proposal within that choice.

- D-NOTIFY-MODEL r3 (proposed, owner: backend developer): Unchanged storage choice (Notification and AlertPreference records, outbox, mock adapter until I-03), extended as a PROPOSAL for the backend developer: AlertPreference holds per-event WhatsApp and email choices, a digest time, quiet hours and a revision, and keeps channel and frequency as summaries; Notification records how and when it was delivered (or why it stayed in the app) and when it was read, and read is changed only by the mark-read write. Retention and storage details stay the backend developer's. — F-12 readiness PMO-0-1: the approved settings board is a per-event matrix with digest time, quiet hours and a verified WhatsApp number, which one channel and one frequency cannot store (design/canvas/project/SCR-15-desktop-settings.dc.html). Screen fields are in D-ALERT-PREFS-VIEW.

- D-ALERT-PROVIDERS r2 (open, owner: business owner with the backend developer): Not chosen; PSL owns the accounts (I-03). Built against a mock adapter until chosen. — Unchanged choice; the decision now belongs to the business owner with the backend developer. The frontend builds against it as a working assumption (design engineer, 13 Nov 2026).

- D-CONVERSATION-MODEL r3 (proposed, owner: backend developer): Unchanged choice (Conversation and Message records per person, cited records and the agent run on each answer, drafts only through the normal line start), extended as a PROPOSAL for the backend developer: a Conversation stores its agent, title, status and project context; a Message stores typed steps, a handoff note, source details, the reason it cannot answer, and a draft with what to start and the started work once started. Retention and storage details stay the backend developer's. — F-12 readiness PMO-0-2: a page reload loses the status today, steps are strings and drafts have no shape (design/canvas/project/SCR-05-desktop-thread.dc.html, -draft-started, -working). Screen fields are in D-ASSISTANT-VIEW.

- D-AGENT-PROVIDER r2 (open, owner: business owner with the backend developer): Not chosen. Real cases refuse unapproved providers today; the synthetic provider is used until approval. — Unchanged choice; the decision now belongs to the business owner with the backend developer. The frontend builds against it as a working assumption (design engineer, 13 Nov 2026).

- D-ROLE-PMO r1 (approved, owner: business owner): One role, PMO Lead. Backend lookups of a separate "Head of PMO" role map to PMO Lead. — Confirmed by PSL through the design engineer on 13 Nov 2026.

- D-APPROVAL-ORDER r1 (approved, owner: business owner): PM, then PMO Lead, then CEO; the CEO approves last. Replaces PM, Head of PMO, CEO, PMO Lead. — Confirmed by PSL through the design engineer on 13 Nov 2026.

- D-LEADERS-START r1 (approved, owner: business owner): Grant the CEO and CTO the start permission on every line; their Start work opens the full menu. No approval step is added for anyone else. — Decided by the design engineer on 13 Nov 2026.

- D-RETURN r2 (open, owner: business owner with the backend developer): Proposed for review: every return creates a "correct and resubmit" task for the preparer. Today accounts, the shared engine and schedules differ. — Unchanged choice; the decision now belongs to the business owner with the backend developer. The frontend builds against it as a working assumption (design engineer, 13 Nov 2026).

- D-FIRST-FEATURE r2 (approved, owner: delivery owner): My work and one decision end to end (J-01 view, J-02): identity, the three queues, the work item with history, claim and decide with stale-version handling; desktop and phone. The frontend is built against the API contract with a mock server and connected to each real endpoint as the backend delivers it. — Accepted by the design engineer, 13 Nov 2026, who builds the frontend only.

- D-TASK-DECISION-VIEW r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm: each E-WORK-ITEM tasks[] entry gains optional fields: decision (exact version label and number, amount as money that may be unknown, basis, recipient, changes since the previous version, preparer, approval chain with "your step n of m"), cannot_act_reason (not_your_role, prepared_by_you, already_decided, not_your_turn) and asked (who was asked instead, when alerted, by which channel). No new endpoint; the backend composes every value from its records and the line's configured approval order; the frontend shows only what is returned. — Smallest change: the decision screen already loads the work item, reuses its read permission and revision, and existing v3 fields and fixtures stay valid because every new field is optional. Unknown amounts use unknown=true with no value, never 0 (INV-UNKNOWN). Approvers and their order come from the backend (D-APPROVAL-ORDER), never from the frontend.

- D-WORKITEM-DETAIL r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm: E-WORK-ITEM gains optional amount (money, unknown form), started_by and started_at; each station gains optional started_at, finished_at and held_by (who or what holds it, and whether that is you); the agent gains optional started_at and each agent step an optional at. — The approved SCR-02 boards show "Started by <person> (<role>) · <date>", station times ("Done · Mon 14:05", "Waiting 2h · you"), agent step times and the agent start time; A-WORKITEM needs an unknown amount. All additions are optional so v3 payloads stay valid.

- D-WORKLIST-FILTERS r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm: E-WORK-LIST accepts project (a case_id) and waiting_on (me, someone_else, agent, outside_party, no_owner) as optional filters; line takes the line key, never the display title; the response gains optional filters.lines[{key, title}] (lines the person can see work on); rows gain optional line_key and agent (the agent whose avatar the row shows). — The approved filter panel (SCR-01-*-filter) offers Line, Project, State and Waiting on, and rows show an agent avatar (CMP-18) when an agent drafted or is working on the item. The waiting_on categories are an engineering proposal read from the board rows, not a business rule. Project options come from E-PROJECTS.

- D-DECISION-VARIANTS r1 (open, owner: business owner with the backend developer): Not designed. Parked until PSL and the backend developer settle the payment-exception rule: what "Keep owed", "Exception" and "Reject" record, which fields and figures (invoiced, received, owed, rule) each variant returns and sends, who holds the authority, and whether the short payment is decided through E-TASK-DECIDE or an exception action. No verdict, rule or approver is assumed here. — A payment exception needs configured human authority and never erases debt (AGENTS.md product invariants); inventing its verdicts would invent a financial rule. The design engineer parked the variants on 13 Nov 2026.

- D-START-INTAKE r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm: (1) each E-LINES line says which case it starts on: case_scope project (the case and its revision come from the chosen option of the field named by case_field) or fixed (case_id and case_revision on the line, e.g. the Finance back-office lines with no Project field); (2) intake[].type takes a defined kind (text, long_text, date, date_range, period, datetime, integer, money, choice, record, records, evidence, display) with help, placeholder, fixed options, depends_on, evidence_kind, display value and restricted; (3) record fields read their options from a new E-LINE-OPTIONS endpoint, filtered by grants on the backend and narrowed by parent; (4) proof is uploaded first with E-EVIDENCE-UPLOAD on the line's case, which now returns the case revision after the upload, and the evidence_id is the intake value; (5) lines carry an optional subtitle, a "what happens next" block (station count, agent, deciding role, summary) and start_via (E-WORK-START, or E-IMPORT for an import line); (6) E-LINES returns default_line for the main button, absent for people whose button opens the menu; (7) /me startable_lines holds line keys; (8) a 422 on E-WORK-START names each field with its message. — The approved SCR-04 drawers (16 lines, desktop and phone, plus validation) show choice lists from records, proof files, money and period fields and a "What happens next" block; v5 gives only key, title, group and name/label/type/required, and requires a case revision no read returns. All additions are optional, so v5 payloads stay valid. Field kinds, options, deciding roles and the default line come from the backend; the frontend derives none of them from roles. A blank money value is unknown, never 0 (INV-UNKNOWN). Whether the management accounts drawer starts through E-WORK-START or E-IMPORT, and E-IMPORT's missing entity, basis, extracted-at and control total, are for the backend developer.

- D-RESPONSE-VIEW r2 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): r1 plus, on tasks[].response: intro, proof_hint, agent_note, the channels a response may have been received by, context (project, document), next lines and a recorded block (by, at, received via, proof count, summary); variants go_live_acceptance and support_handover (go-live signatures recorded by the PM, Support's reply recorded by the PM); E-RESPONSE accepts received_via and returns revision, recorded and next. — F-09 readiness PMO-0-1: design/canvas/project/SCR-16-desktop.dc.html:20 (intro), :34 (proof hint), :46-47 (Tola's aside), SCR-16-desktop-success.dc.html:17 ("received by email", recorded by and at, "1 proof file", what happens next), SCR-16-desktop-sow-signed.dc.html:17 (project crumb, "the SOW's 4 stages become the project's milestones"); SCR-45-desktop-signatures.dc.html and SCR-48-desktop-record.dc.html record go-live signatures and Support's reply. Every sentence is composed by the backend from records, so the mock can hold it under additionalProperties false.

- D-WORK-ACTIONS-VIEW r2 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): r1 plus reconcile.unknown_note and reconcile.resend_note, and an optional case_revision on E-WORK-ACTION for the proof upload that precedes a reconcile. — F-09 readiness PMO-0-1 and PMO-0-5: design/canvas/project/SCR-02-desktop-awaiting-reconciliation.dc.html:17 ("Keep it held and remind me tomorrow", "A resend reuses the same invoice number"); E-EVIDENCE-UPLOAD says to send its case_revision on the action that follows, which E-WORK-ACTION could not carry. What "can't tell yet" does and what a resend reuses are backend rules stated by the backend.

- D-RFP-OUTCOME r2 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): r1 plus an RFP frame on the work item (reference, title, client, status tag with days left, PM, five tabs with counts), and on rfp_outcome: lesson categories, a recorded block with what's recorded rows, reminder holder and time, categorised lessons, the debrief proof, the archive reference, the engagement created and next lines, and a follow-up the agent drafted (recipient as returned, body, version, checks, status, can send, can edit). A new POST /api/v1/work/{work_id}/rfp-outcome/followup sends that draft (optionally edited) with the expected revision, draft version and an idempotency key; an unknown outcome returns effect_uncertain and blocks a resend until reconciled. E-RFP-OUTCOME accepts lessons_items. — F-09 readiness PMO-0-2: design/canvas/project/SCR-16-desktop-team-input.dc.html:17 and -rfp-outcome.dc.html:17 (frame: "DEADLINE 28 NOV · 16 DAYS", "PM TUNDE BELLO", "Requirements 64", "Team input 2/4"), SCR-16-desktop-rfp-lost.dc.html (PRICE, TIMELINE, STRENGTH lessons, "Debrief notes (proof)", ARC-0117), SCR-16-desktop-rfp-won.dc.html ("Engagement EN-0042 created"), SCR-16-desktop-rfp-pending.dc.html ("Reminder for Tunde Bello · 10 DEC 09:00"), SCR-16-desktop-rfp-unknown.dc.html (follow-up to the procurement address, "It goes only if you send it", Send follow-up, Edit). The send is external messaging, so it is a person's action with idempotency and uncertain-effect handling (INV-RESEND, INV-AGENT); the email provider stays open (D-ALERT-PROVIDERS). Who may send is a backend rule.

- D-PROJECT-TAB-ROWS r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm: E-PROJECT-TAB rows are typed per tab, in an optional array named by the tab (the untyped v5 items stays and holds the same rows): milestones (position, name, contract amount, completion with proof, invoice, paid, changes with their own amount), documents (document, version, status, test template), money (stage, amount, invoice and its status, paid, the E-REPORT figure that explains it), registers (register, reference, title, severity, owner, state, age; filtered by register and q) and actions (title, from which meeting, owner, due date or unknown, open/overdue/done); a summary carries register and action counts and the money report id. E-PROJECT gains optional revision and tab counts; E-REPORT figures gain an id and source details (document, rule, record, evidence). — The approved project tab boards show these columns; v5 rows are untyped ("documented in handoff", never documented). Every amount uses the money form with unknown=true and no value when unknown, never 0, and paid is Finance data separate from the invoice (INV-UNKNOWN, INV-FACTS). Paid status categories and owed amounts are composed by the backend from receipts and allocations, not by the frontend. The documents tab has no approved list board, so its row is an engineering proposal.

- D-EXCEPTIONS-LIST r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): E-EXCEPTIONS accepts optional q (search over title, reference, what is being done, who acts) and what (one kind); the response gains optional open_count (all matching rows the person may see, across pages) and each row an optional ref (the work's business reference). — Boards: design/canvas/project/SCR-10-desktop.dc.html (search, Filter, "4 OPEN", reference under the title), SCR-10-mobile.dc.html ("Exceptions · 4"). Same names as the F-06 round-2 mock (delivery/features/F-06/round-2/build.md), so its fixtures need no rename. A count the backend does not send is not shown, never guessed.

- D-MONTH-END-VIEW r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): E-MONTH-END gains optional as_of and coverage, a summary (done, waiting, in progress, total) composed by the backend, cash_received_detail (the known part plus has_unknown), an agent note and a next action (label, work_id); each task gains optional title, detail, status_label, tone, restricted and restricted_label (restricted rows carry no work_id). cash_received keeps its v6 shape. — Boards: design/canvas/finance/project/SCR-36-desktop.dc.html (as-of line, four-cell strip "2 of 7 / 3 / 2", "Cash received ₦4.7M + Unknown", task detail and "NEEDS FINANCE DECISION" tags, "HR only" row, Chidi's note, "Import the missing statement") and SCR-36-mobile.dc.html. v6 money is all-or-unknown and cannot say "known plus Unknown" (F-10 readiness PMO-0-1). Which month is being closed, what is restricted and every amount are backend facts; the frontend buckets nothing.

- D-LINE-WORKSPACE r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): E-WORK-ITEM gains an optional workspace block for the line-specific content of every line screen: line key, screen and board state, title, status, byline, version, project context, an agent note, typed sections (facts, table with typed cells, checklist, findings, suggestions, recipients with receipts, figures, text with cited records, timeline) and the steps this person may take now, each with typed fields (the E-LINES field descriptor) and its consequence sentence. Decisions inside a workspace stay on E-TASK-CLAIM/E-TASK-DECIDE (a step carries task_id); responses stay on E-RESPONSE; reconcile stays on E-WORK-ACTION. Every other line step goes through one new POST /api/v1/work/{work_id}/steps with the step key, item ids, typed inputs, proof, expected revision and an idempotency key; a step that sends and cannot confirm the send returns effect_uncertain. — The 27 screens with no task (delivery/screen-coverage.md) and the Finance line screens (F-10 readiness) are line workspaces: e.g. design/canvas/project/SCR-25-desktop-review.dc.html (report sections citing records, "2 RECORDS", "Approving sends this exact version"), SCR-26-desktop.dc.html (requirements matrix with suggestions to accept, edit or reject), SCR-28-desktop-suggesting.dc.html (suggested decisions and actions with owner and due date), SCR-31-desktop-impact.dc.html (impact per team), SCR-44-desktop-readiness.dc.html (readiness checklist), SCR-45-desktop-signatures.dc.html (signatures), SCR-46-desktop-evaluating.dc.html (criteria), SCR-49-desktop-blocked.dc.html (closure blockers), SCR-52-desktop-received.dc.html (receipts per recipient), and design/canvas/finance/project/SCR-53..SCR-59 (quarantine findings, review results, schedules by class with Unknown, recipients and receipts). One shared block avoids about 25 endpoints and follows the v6 reconcile and rfp_outcome pattern. Which sections and steps exist, their values, who may take a step and what it does are backend rules; the frontend renders by kind and offers only returned steps. Restricted sections return restricted=true and no rows (INV-RESTRICTED); unknown amounts and dates use the unknown form, never 0.

- D-RFP-INTAKE r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): a received RFP starts on a fixed pre-sale intake case the backend names on the line (D-START-INTAKE case_scope fixed), because E-WORK-START requires a case and a new RFP has none; the work item gains an optional assign block (role, candidates, note required) when this person may assign, and a new POST /api/v1/work/{work_id}/assignment records the choice. — Boards: design/canvas/project/SCR-23-desktop.dc.html / -mobile (log a received RFP), SCR-24-desktop.dc.html / -mobile (assign the accountable PM from the Unassigned queue). Who may assign ("who may assign an RFP" is a Setup rule) and who the candidates are come from the backend. Whether the backend instead creates the case on start is for the backend developer.

- D-SETUP-RULES-VIEW r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): E-SETUP-RULES rows gain optional area and group (with labels), used_by, display_value (absent when Not set), link, holds_work, effective_from, can_change, restricted and an editor (role_set with role options, or read_only); the response gains not_set_count and roles_missing_count. E-SETUP-RULE-SAVE accepts expected_revision 0 for the first version of a rule that is Not set (v6 required at least 1, which made A-SETUP impossible) and optional starts, reason and evidence_id. A read-only GET /api/v1/setup/costing-rule returns the rule's versions, its content as typed sections, worked examples and the review work item, for display only. — Boards: design/canvas/project/SCR-13-desktop-rules.dc.html ("Save as version 1", Roles allowed, Starts, Why, Proof, HOLDS WORK), SCR-13-desktop-finance-rules.dc.html (groups, NOT SET), SCR-13-desktop-delivery-rules.dc.html (USED BY), SCR-39-desktop.dc.html / -review / -example / -review-own (costing versions and examples) and their mobile boards. Only the role-list editor is drawn, so other value kinds stay read-only. Edit controls follow can_change, never /me roles; a missing value is Not set, never a default (REC-CONFIG). How the costing rule is proposed, reviewed and withdrawn is open (D-COSTING-RULE), so no costing write is proposed.

- D-DELEGATION-VIEW r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): a new GET /api/v1/setup/delegations lists the delegations the person may see (from, delegate, authority, starts, ends, reason, status, can_change, revision) with the authorities and delegate options the backend allows; E-DELEGATION gains optional authority and reason. — Boards: design/canvas/project/SCR-13-desktop-delegation.dc.html and SCR-13-mobile-delegation.dc.html show current and scheduled delegations; v6 E-DELEGATION is a PUT with nothing to read (F-11 readiness, F-11B). Which authority may be delegated and to whom is the backend's rule.

- D-PEOPLE-VIEW r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): E-PEOPLE rows gain optional person_id, email, scopes, state (active, invited, deactivated), last_signed_in_at, open_items, can_change and revision, and the response the missing roles (with held work) and role options; three proposed writes assign roles (optionally resuming held work), invite a staff member and deactivate an account with reassignment of open items. The writes are gated by D-ADMIN-AUTHORITY; invite also depends on D-SIGNIN. — Boards: design/canvas/project/SCR-13-desktop.dc.html ("Roles · 2 missing"), SCR-13-desktop-validation.dc.html ("Assign and resume held work"), SCR-13-desktop-permission.dc.html, SCR-21-desktop.dc.html, SCR-21-desktop-invite.dc.html, SCR-21-desktop-deactivate.dc.html and their mobile boards. Who holds Admin and who may assign roles is PSL's to name (design/screens.md); the contract carries only what the backend allows.

- D-TEMPLATES-VIEW r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): E-TEMPLATES rows gain optional template_id, kind, updated_at, updated_by, versions, revision and can_upload; a new POST /api/v1/setup/templates/{template_id}/versions uploads a new version with the expected revision; test_template is returned by the backend, never set by the frontend. — Boards: design/canvas/project/SCR-34-desktop.dc.html and SCR-34-mobile.dc.html (versioned upload). PSL supplies real templates; until then they are test templates (13 Nov decision).

- D-ALERT-PREFS-VIEW r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): a new GET /api/v1/me/alert-preferences returns the v6 channel and frequency plus revision, per-event rows (key, label, WhatsApp, email, timing), digest time and quiet hours with their options, and the WhatsApp number masked with its verified flag; PUT accepts optional expected_revision, events, digest_at and quiet_hours and keeps channel and frequency required; E-NOTIFICATIONS accepts optional q, agent and unread and returns total and unread_count, each alert its reference, how and when it was delivered, its digest time and why it was in the app only; a new POST /api/v1/notifications/{id}/read marks one alert read. — Boards: design/canvas/project/SCR-15-desktop-settings.dc.html (WHEN / WHATSAPP / EMAIL / TIMING rows, "Daily digest at 08:00", "Quiet hours 20:00 to 07:00, and weekends", "+234 803 *** 4412 · verified"), SCR-15-mobile-settings.dc.html, SCR-15-desktop.dc.html ("4 ALERTS", "WhatsApp and email · 10:42", "In app only (you are not HR)", NEW). Which events exist, which channels a restricted alert may use and what quiet hours suppress are backend rules. The number is never unmasked. Keeping channel/frequency as required summaries is the additive choice; whether to retire them is for the backend developer (F-12 PMO-0-1 e).

- D-ASSISTANT-VIEW r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): a conversation list (title, agent, status, status line, updated), the conversation's agent, title, status and context (project, "Your access"), per message typed steps (done, now, next, with a record reference), a handoff note, source details with links, why it cannot answer, and a draft (title, label/value rows, status label, what to start: line, case, revision and intake prefill for the normal Start work drawer, and the started work once started); E-MESSAGE accepts mentions, with a new mention search over records the person may read; /me lists the agents this person may talk to. — Boards: design/canvas/project/SCR-05-desktop.dc.html (side list "Drafted · ready to start", "Working · step 3 of 5"), SCR-05-desktop-thread.dc.html (steps, sources, draft rows with "₦6,800,000.00"), SCR-05-desktop-draft-started.dc.html, SCR-05-desktop-cant.dc.html ("Can't share"), SCR-05-desktop-working.dc.html and their mobile boards. A draft starts only through E-WORK-START (D-CONVERSATION-MODEL); answers use only records the person may read (INV-RESTRICTED). Attachments and speech input are not proposed (D-SPEECH-INPUT open).

- D-PROJECTS-VIEW r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): E-PROJECTS accepts an optional status (active, closed, all) and returns counts per status and a total; rows gain reference, next milestone (name, due or unknown), needs_person and stopped counts. E-PROJECT gains pm, route, work and line counts, a facts strip, an agent summary, per-line reference, title, detail, station, status label and tone, and a delivery block (one row per delivery line with its gate status) for the delivery overview. — Boards: design/canvas/project/SCR-22-desktop.dc.html (Active / Closed / All I can see tabs with counts, NEXT MILESTONE, NEEDS A PERSON, STOPPED, "5 PROJECTS"), SCR-07-desktop.dc.html (PM and route sub-line, six-cell facts strip, RFP-0031, "Station 2 of 5 · client UAT", Tola's summary), SCR-43-desktop.dc.html (six delivery lines with gate status). F-07 left these out because v6 had no field (delivery/features/F-07/round-1/build.md). Counts are composed from authorised records by the backend, never by the frontend.

- D-OVERVIEW-VIEW r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): each E-OVERVIEW line gains an optional key, subtitle, agent and status (label and tone). — Board: design/canvas/project/SCR-06-desktop.dc.html (lines "Pre-sale · RFP · commercial · 1 WAITING", "Payroll · Restricted · 2 PROBLEMS", "ON TRACK"). F-08 drew no avatar, subtitle or tag colour because v6 had none (delivery/features/F-08/round-1/build.md PMO-0-4). Tones are display hints chosen by the backend.

- D-RECEIVABLES-VIEW r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): a new GET /api/v1/finance/invoices lists invoices with invoiced, received and owed (each may be unknown), status, reminder and totals, filtered by q, status and client; a new POST /api/v1/finance/invoices/{id}/receipts records one receipt (known amount, date, bank reference, proof, idempotency key) and returns the allocation status the backend composed. The payment reminder (SCR-32) is the reminder line's workspace (D-LINE-WORKSPACE). The short-payment decision stays parked (D-DECISION-VARIANTS). — Boards: design/canvas/finance/project/SCR-20-desktop.dc.html (invoiced, received, owed with Unknown), SCR-20-desktop-record.dc.html (record a payment with bank reference and proof), SCR-32-desktop.dc.html (reminder draft, edit, send) and their mobile boards. Stages, invoices, receipts and allocations are separate (AGENTS.md); how a receipt is allocated and what a short payment does are not decided (D-RECEIPT-ALLOCATION, D-DECISION-VARIANTS), so the receipt write is gated and nothing here erases debt.

- D-CLIENTS-VIEW r1 (proposed, owner: backend developer): PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): a client list (name, projects, owed, billing contact set), a client detail (billing contact, projects, money, what is blocked) and a PUT that sets the billing contact with the expected revision. — Boards: design/canvas/project/SCR-35-desktop.dc.html, SCR-35-desktop-detail.dc.html and their mobile boards (billing contact that blocks invoices until set). Where client records live in the backend is for the backend developer (REC-CLIENT is proposed).

- D-SIGNIN r1 (open, owner: backend developer): Not decided. D-AUTH keeps the Django session; whether the Next.js app renders sign-in through new session endpoints or the Django sign-in pages are styled to the boards, and how reset and invite set-up work, are for the backend developer. No sign-in endpoint is proposed. — Boards: design/canvas/project/SCR-17-desktop.dc.html, -error, -reset, -setup and their mobile boards; SCR-15-desktop-account.dc.html "Sign out". Sign-in is a security boundary; designing it from the frontend would set the backend's auth design.

- D-ADMIN-AUTHORITY r1 (open, owner: business owner): Not decided. PSL names who holds Admin and who may assign roles, invite and deactivate staff; Admin confers no approval authority (guide/10-POLICY-CONFIGURATION.md). The proposed writes stay gated until then. — design/screens.md lists "who holds Admin" for PSL to confirm; F-11 readiness F-11C. Inventing it would name approvers.

- D-PAYROLL-VISIBILITY r1 (open, owner: business owner): Not decided. Proposed shape only: payroll field visibility would be Setup rules in area payroll_visibility with a role_set editor, read through E-SETUP-RULES. Which fields are configurable and that the HR Lead decides are for PSL to confirm; INV-RESTRICTED stays enforced by the backend whatever is configured. — Boards: design/canvas/project/SCR-13-desktop-fields.dc.html and SCR-13-mobile-fields.dc.html. Restricted payroll data is a security boundary owned by HR (F-11 readiness F-11E).

- D-COSTING-RULE r1 (open, owner: business owner with the backend developer): Not decided. How a costing rule version is proposed, who reviews it (the proposer may not review their own, 12 Nov), how worked examples are checked, how a version is withdrawn, and the backend change to one studio-wide rule are for PSL and the backend developer. v7 proposes only a read for display (E-COSTING-RULE). — Boards: design/canvas/project/SCR-39-desktop.dc.html, -review, -example, -review-own; SCR-27-desktop.dc.html, -adjust, -ask, -approvals. Costing is a financial rule; design/screens.md notes "backend change needed".

- D-CHANGE-DECIDERS r1 (open, owner: business owner): Not decided. Whether a change request needs all five deciders drawn or only some, and in which order, is for PSL; the decision view shows only the chain the backend returns (D-TASK-DECISION-VIEW). — Board: design/canvas/project/SCR-31-desktop-decision.dc.html and -authorise ("does the change need all five deciders or only some?", delivery/screen-coverage.md).

- D-RECEIPT-ALLOCATION r1 (open, owner: business owner with the backend developer): Not decided. How a receipt is allocated to invoices and stages, what happens on a part payment, and which role records receipts are financial rules for PSL and the backend developer. The receipt write stays gated; payment exceptions stay under D-DECISION-VARIANTS and never erase debt. — Board: design/canvas/finance/project/SCR-20-desktop-record.dc.html. Receipts and allocations are separate records (AGENTS.md product invariants).

- D-SPEECH-INPUT r1 (open, owner: business owner): Not decided. Browser speech recognition can send audio to the browser maker, an external connection not authorised in this phase. Options: build the control wired to nothing, use an approved local engine, or record a fidelity exception. — Boards: design/canvas/project/SCR-05-desktop.dc.html and SCR-05-mobile.dc.html composer (F-12 readiness PMO-0-9).

- D-ALERTS-ENTRY r1 (open, owner: design engineer): Not decided. No approved board draws the bell (only the site map says "Bell, top right"); the account menu links "My roles" and "Delegate while away" to nothing, and no phone board shows how the account page opens. — Boards: design/canvas/project/SCR-15-desktop-account.dc.html, SCR-15-mobile-account.dc.html, SITEMAP-desktop.dc.html (F-12 readiness PMO-0-6, PMO-0-7). A drawing question for the design engineer, not a backend rule.
