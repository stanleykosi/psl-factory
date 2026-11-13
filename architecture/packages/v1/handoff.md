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
    "REC-CONVERSATION"
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
    "REC-CONVERSATION"
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
    }
  ],
  "notes": "New records: notification, alert preference, conversation."
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
    "E-WORK-ITEM"
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
    "E-RESPONSE"
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
    "E-SETUP-RULE-SAVE"
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
    "A-ME"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
            }
          },
          "csrf_token": {
            "type": "string",
            "minLength": 1
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
    "A-MYWORK"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
        "minLength": 1
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
    "A-WORKITEM"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
                  "minLength": 1
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
                    }
                  },
                  "required": [
                    "text",
                    "status"
                  ],
                  "additionalProperties": false
                }
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
    "A-START"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
                        "minLength": 1
                      },
                      "required": {
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
    "A-START"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
        "additionalProperties": true
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
    "A-RESPONSE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
  ],
  "method": "POST",
  "path": "/api/v1/cases/{case_id}/evidence",
  "trigger": "File drop in a form",
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
    "A-RESPONSE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
    "A-RECONCILE"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
    "A-RESUME"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
    "A-PROJECT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
    "A-PROJECT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
    "A-PROJECT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
    "A-OVERVIEW"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
    "A-MONTHEND"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
    "A-SETUP"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
    "A-SETUP"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
        "minimum": 1
      },
      "value": {
        "type": "object",
        "additionalProperties": true
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
    "A-SETUP"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
  ],
  "method": "GET",
  "path": "/api/v1/setup/people",
  "trigger": "Setup people",
  "security": [
    "Session"
  ],
  "permission": "Admin.",
  "parameters": [],
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
    "A-SETUP"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
    "A-SETUP"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
    "A-ALERTS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
    "A-ALERTS"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
        ]
      },
      "frequency": {
        "type": "string",
        "minLength": 1,
        "enum": [
          "immediate",
          "daily"
        ]
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
    "A-ASSISTANT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
    "A-ASSISTANT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
    "A-REPORT"
  ],
  "evidence": [
    "S-SCREENS",
    "S-BACKEND"
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
                }
              },
              "required": [
                "label",
                "value",
                "sources"
              ],
              "additionalProperties": false
            }
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

## Decisions and client inputs

- D-API-STYLE r1 (proposed, owner: technical reviewer): Plain Django JSON views under /api/v1 in a new apps/api package that call the existing service functions; no new framework. — Every write already goes through service functions with expected revisions; a thin JSON layer reuses them and adds no dependency.

- D-AUTH r1 (proposed, owner: technical reviewer): Same-origin deployment: the Next.js app and /api/v1 are served behind one host; the Django session cookie authenticates; writes send the CSRF token header. — C-05 says people sign in once and Django keeps login; same origin avoids CORS and token storage in the browser.

- D-HOSTING r1 (open, owner: release authority): Not chosen. Needed before the first release, not before local development. — No deployment is authorised in this phase.

- D-UPDATES r1 (proposed, owner: technical reviewer): Polling: lists every 15 seconds while visible, an open work item every 5 seconds while an agent is working; no push channel in v1. — Simple and works with session auth and the existing request model; push can follow if volume demands it.

- D-PAGING r1 (proposed, owner: technical reviewer): Cursor paging, 50 rows per page, newest activity first; counts per queue returned separately. — C-06 high volume; matches the "Show more" pattern in the design.

- D-NOTIFY-MODEL r1 (proposed, owner: technical reviewer): Add Notification (per person, per work item event) and AlertPreference (channel WhatsApp/email/both, frequency) records; sends go through the existing outbox to a mock adapter until I-03 is connected. — No notification or preference model exists; the outbox pattern already handles uncertain sends.

- D-ALERT-PROVIDERS r1 (open, owner: business owner): Not chosen; PSL owns the accounts (I-03). Built against a mock adapter until chosen. — Accounts, templates and opt-in belong to PSL.

- D-CONVERSATION-MODEL r1 (proposed, owner: technical reviewer): Add Conversation and Message records per person; each assistant answer stores the records it cited and the agent run it came from; drafts are created only through the normal line start. — No conversation model exists; R-08 requires sources on every answer and drafts in their normal line.

- D-AGENT-PROVIDER r1 (open, owner: business owner): Not chosen. Real cases refuse unapproved providers today; the synthetic provider is used until approval. — Live AI activation is not authorised in this phase.

- D-ROLE-PMO r1 (approved, owner: business owner): One role, PMO Lead. Backend lookups of a separate "Head of PMO" role map to PMO Lead. — Confirmed by PSL through the design engineer on 13 Nov 2026.

- D-APPROVAL-ORDER r1 (approved, owner: business owner): PM, then PMO Lead, then CEO; the CEO approves last. Replaces PM, Head of PMO, CEO, PMO Lead. — Confirmed by PSL through the design engineer on 13 Nov 2026.

- D-LEADERS-START r1 (approved, owner: business owner): Grant the CEO and CTO the start permission on every line; their Start work opens the full menu. No approval step is added for anyone else. — Decided by the design engineer on 13 Nov 2026.

- D-RETURN r1 (open, owner: business owner): Proposed for review: every return creates a "correct and resubmit" task for the preparer. Today accounts, the shared engine and schedules differ. — Raised in the Finance audit.

- D-FIRST-FEATURE r1 (proposed, owner: delivery owner): My work and one decision end to end (J-01 view, J-02): session and identity, the three queues, the work item with history, claim and decide with stale-version handling; desktop and phone. — Smallest slice that exercises the API seam, permissions, revisions and the design system on real records.
