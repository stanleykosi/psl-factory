# PSL answers to the frontend connection questions

PSL confirmed these answers on 23 November 2026. The numbers match the developer’s thirteen priority questions. The five follow-up decisions are included in questions 1, 11 and 12. The original questions retain their screen IDs. [Frontend developer’s questions](backend-questions.md)

## 1. Proof and attachments

**PSL’s answer.** The current PMO Lead can approve a step that belongs to them directly. Their signed-in approval is the record of that decision. Show **Approved by PMO Lead**, the approver’s name and the time. A separate written note or duplicate signature from the PMO Lead is optional. Other staff attach a copy of the signed PDF where proof is required. The agent identifies the attachment for review. Client signatures, Finance approvals and other independent decisions continue through their own steps.

**Backend.** Upload the file to the project, then attach its `upload_id` using `POST /work/{work_id}/proofs`. The backend checks the original file, preserves its hash, returns an evidence ID, and records who attached it and to which work item. The written-note route checks current PMO Lead authority. Reviewed file-agent drafts expose `reviewed_evidence_id` for their native handoffs. Work attachments are available for work history and delivery observations. The new direct PMO Lead approval rule still needs to be applied to the relevant approval steps. For those steps, the frontend should use the backend’s permission and show the recorded approval once it succeeds.

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

**PSL’s answer.** Wait until Finance knows the actual amount received and where the payment came from before a new receipt is recorded. Finance should identify the source of a statement or other file before uploading it, then match the transaction to its original proof. If the amount is missing, staff check the source or ask for confirmation first.

**Handoff.** The missing amount is the amount of money actually received on that transaction. The backend already has an invoice-linked **Record payment** flow at `GET/POST /projects/{case_id}/invoices/{issue_id}/payments`. The form accepts the payment source and transaction reference, with the original private bank statement. Next.js should expose that flow from Finance payments or the invoice detail. The API still permits a new receipt with an unknown amount, so both the server and the form need to enforce the new rule. Keep earlier incomplete receipts and their current correction path. The amount and source are needed at intake, and verification and allocation remain distinct Finance actions. The Payments API already reports known amounts owed and counts of items with unknown balances.

## 12. Designed features that need backend data

**PSL’s answer.** Provide a backend for the agreed features. The follow-up decisions below define how staff use images, report notes and alerts.

- **Tola’s notes and findings.** Use the recorded work activity and evidence links. Detailed, authorised agent notes on individual work lines still need line-specific mappings.
- **Report notes and comparison.** Keep each agent note beside the report section it refers to, visible to staff authorised to review the draft. The approved report sent to a client or Support leaves out those notes. The compare endpoint already returns changed, added, removed and unchanged sections for authorised versions of the same standalone report and audience, with the evidence IDs. Storing and showing the review-only notes still needs implementation.
- **Alerts.** Keep the alert inbox and add a daily summary inside PSL Factory. Email and WhatsApp remain deferred. Quiet hours, notification switches by event, and external summaries can be addressed when those channels are connected. The in-app daily summary still needs implementation.
- **Assistant images.** Staff can attach images to questions for Tola, Chidi or Zainab. Send the images they attach with the question to OpenRouter. The agent should read them together with the current files and records the person can use for that question before answering. Existing project, role and report access governs that context. Project file upload exists. The attachment link, OpenRouter image reading, combined evidence and answer citations still need to be wired and tested.
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

The five follow-up questions have answers. The remaining work is implementation and release verification.

| Frontend flow | Expected behavior | Backend status |
| --- | --- | --- |
| Ask an assistant with an image | Attach the image, send it with the question, and show the answer with its permitted project sources. | File upload exists. Image links to messages and OpenRouter image reading are pending. |
| Review a report | See the agent’s notes beside each section during staff review. The outward version contains the approved report. | Version comparison and evidence links exist. Section notes are pending. |
| Check daily alerts | Open a daily summary inside the app and follow the items to the original alerts. | Personal alerts exist. The daily summary is pending. |
| Approve a PMO step | The current PMO Lead approves their own step directly and can add a note if useful. Show the recorded role, person and time. | Proof attachments exist. The direct approval rule needs to be wired to eligible steps. |
| Record a payment | Use a Finance entry point and require the real amount and payment source before recording it. | Invoice-linked receipt intake exists. The new checks and Next.js entry point are pending. |

The backend changes are on `codex/backend-handoff-answers`, based on GitHub main at `924e7cdc`. Next.js sign-in and sign-out have since merged to main at `8f562602`. The OpenAPI 1.23.0 snapshot describes the routes already implemented and tested locally against PostgreSQL. The branch contains the Emergency outcome database migration. Use the deployed contract during Railway testing. The Railway release and Next.js integration are pending. [OpenAPI snapshot](../../contracts/psl-factory.openapi.json) · [Test ledger](../../BUILD-TESTS.md)
