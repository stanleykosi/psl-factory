# PSL answers to the frontend connection questions

PSL gave these answers on 23 November 2026. The numbers match the developer’s thirteen priority questions. The original questions retain their screen IDs. [Frontend developer’s questions](backend-questions.md)

## 1. Proof and attachments

**PSL’s answer.** Upload a copy of the signed PDF. The current PMO Lead can provide a written note in place of a file. Other staff must supply the signed PDF. The agent should identify the attachment for review.

**Backend.** Upload the file to the project, then attach its `upload_id` using `POST /work/{work_id}/proofs`. The backend checks the original file, preserves its hash, returns an evidence ID, and records who attached it and to which work item. The written-note route checks current PMO Lead authority. Reviewed file-agent drafts already expose `reviewed_evidence_id` for their native handoffs. Determining whether a copy includes the right signatures remains a human check. Native milestones, client sign-off and Finance commands still require their exact evidence types. The new work attachment is available for work history and delivery observations.

## 2. Work progress

**PSL’s answer.** The API should report the current step, what the agent has done, approvals and what was sent. Staff should see those facts on screen.

**Backend.** Work detail provides `tracking_url` with a common station track, the latest recorded activity, available evidence references, and links to worker, decision and evidence history. Invoice work uses the actual draft, review and delivery receipt. Controlled publications use their exact approved version and recipient receipts. A worker finishing an attempt does not verify the business result. A field with no corresponding record can be unknown. Some specialist lines still need dedicated status and citation mappings to populate every fact.

## 3. What a work screen shows

**PSL’s answer.** Give the next person enough information to understand the item and let them click through for the details. PSL asked for a proposed standard.

**Proposed standard.** Show the reference and project, current step, responsible person or role, why the item is waiting, and the next action. The details show the original source, recorded decisions, agent activity and verified receipt where available. Use the current actor’s permitted actions from the backend. Each line can show additional fields that belong to its work.

**Backend.** Work detail includes the common fields and gives each panel its `contract_path` in OpenAPI. Use the schema for that path and the typed command request for each action. Forecast results, BU results and project tab rows already have typed shapes on main. Some line panels still need richer information or exact choices for their current records.

## 4. Company Setup

**PSL’s answer.** An Admin manages settings across the company. Company-wide settings should be accessible from Setup without needing to know a project first.

**Backend.** `GET /setup/scopes` lists the organisations in the signed-in Admin’s current delegation and the workspace settings the person can open. The existing policy-scope operations create and activate organisation versions, then apply them under the native authority checks. The current write contract anchors policy versions to an authorised workspace. Admin scope follows the company and its real configuration. Independent approval, protected Finance/HR sources and other organisations keep their own access rules.

## 5. Totals and page size

**PSL’s answer.** Show accurate totals. The frontend can decide the page sizes to offer. PSL mentioned 10 or 15.

**Backend.** The work queue accepts `limit=8|10|15|20|50`. It returns the chosen size and reports a total for Started by me and Active work, or for a filtered queue when all candidates fit in the evaluated page. It can skip up to two empty candidate pages per call within the read limit. Use the returned page and next-page values. A null total means the backend cannot show the full tab total yet. Overview counts active work by line.

## 6. Role words and the menu

**PSL’s answer.** Use the staff member’s assigned role for “Finance Lead” and the project name for “Lagoon Health.” The backend should supply the role and accessible workspaces. The frontend decides how to present them.

**Backend.** `GET /me` includes the same `positions` as `GET /role-dashboard`. Each position carries its role name and workspace. Destinations have a Next.js path and an availability flag. API commands still check the person’s permissions for the chosen record.

## 7. Reference numbers and status codes

**PSL’s answer.** Provide a real reference such as INV-0412 and stable status codes.

**Backend.** Work list and detail now expose the original `reference` where available, and the existing `state` and `line` fields are machine-readable. Filter the queue with `state` and display `status_label` to staff. Project tabs expose a stable section `key` and each row’s `state_code`. Restricted report recipients retain the access granted by their report, and references are omitted where the generic queue cannot safely expose them.

## 8. Start work forms

**PSL’s answer.** The API defines the fields for each intake. The frontend uses that definition to build and present the form.

**Backend.** `GET /lines` now returns the exact `request_schema`, submit endpoint and content type for each available line. Invoice intake is the `pmo-finance/v1` line and has two existing modes. Use the projects and source-options links for the staff member’s choices. Use the organisation options for the new received-bid upload.

## 9. Dropdown choices

**PSL’s answer.** The API should expose allowed reasons, stages, approval statuses and other valid choices.

**Backend.** Use the supported values in the matching request schema for fixed choices and the authorised options endpoints for live records or role-dependent choices. This includes Start work forms. The frontend controls labels and layout. Some specialist panels still need dedicated option lists tied to their current records.

## 10. Uncertain delivery

**PSL’s answer.** An authorised person can record what happened when the system cannot determine whether something was sent.

**Backend.** `POST /work/{work_id}/delivery-observations` records delivered, not delivered or unknown with a work-bound proof and a reason. The backend checks current recovery authority and work revision. It preserves the observation and the provider’s original send separately. The existing reconciliation command resolves the original receipt. A human observation alone does not resend, verify or approve an effect.

## 11. Unknown amounts

**PSL’s answer.** PSL asked the backend to handle this and did not choose a new Finance policy.

**Backend.** The current Finance rule permits a reported receipt whose amount is unknown. Verification and allocation require an amount and the existing evidence. The Payments API now returns the known amount owed and count of items with unknown amounts for the displayed currency and basis, alongside the existing complete total. An unknown amount stays unknown.

## 12. Designed features that need backend data

**PSL’s answer.** Provide a backend for each named feature.

- **Tola’s notes and findings.** Use the recorded work activity and evidence links. Detailed, authorised agent notes on every individual line still need line-specific mappings.
- **Document comparison.** The compare endpoint returns changed, added, removed and unchanged sections for authorised versions of the same standalone report and audience. It includes each displayed section’s evidence IDs. Per-section agent notes still need a durable source.
- **Alerts.** Staff alerts remain in the app under the earlier decision. Email and WhatsApp delivery are deferred. Quiet hours, digest times and event-level preferences need their own backend settings and behavior.
- **Assistant images.** Project file upload exists. Attaching an image directly to a question needs an authorised link from the private file to the message and controlled model reading.
- **Delivery overview.** `GET /projects/{case_id}/delivery-overview` lists all six Delivery lines, the latest visible work, its reference, state, update date and work link. A line with no visible work keeps those fields empty. Open the linked line panel to read individual gate decisions.
- **Publish to Support.** `GET /work/{work_id}/support-publication` supplies the current publish-ready flag and document version. POST uses the exact approved version and the configured publisher. The recipient’s receipt remains a separate record.
- **Finance confirmation at closure.** The new Finance confirmation read and write use the actual milestone-notification inventory and original receipts. They require current Finance authority.
- **Emergency impact.** The outcome captures the reported number of customers affected and the side effects as separate fields. Earlier records and unknown values stay empty.

## 13. Hosting and links

**PSL’s answer.** The Next.js team owns the frontend. Give them the Railway details after the backend changes and contract are ready.

**Backend.** Use the Next.js server’s same-origin proxy to reach the Django API and private files. Only an approved exact frontend origin belongs in `PSL_FRONTEND_ORIGINS`. The API sends people to Next.js sign-in and work paths. On the API-only service, old Django pages return a retired-page error. The older preview remains available through its separate URL configuration for controlled verification. A final public frontend origin must come from the Next.js deployment before updating Railway.

## A-55 and A-56

- **A-55.** All six backend download routes return JSON 401 to signed-out staff. The application leaves sign-in to Next.js. Each download still checks current access to the exact file.
- **A-56.** An Admin who has staff-administration authority can sign in and read the role dashboard without choosing an invitation duration. A historical delegation that enabled invitations without a duration keeps its administration scope and has invitations disabled. A new delegation must specify a duration when enabling invitations.

## Handoff package

The code is on `codex/backend-handoff-answers`, based on GitHub main at `924e7cdc`. The OpenAPI 1.23.0 snapshot is generated from the backend routes. The branch contains the Emergency outcome database migration. It has been tested locally against PostgreSQL. The Railway release and Next.js integration are pending. [OpenAPI snapshot](../../contracts/psl-factory.openapi.json)
