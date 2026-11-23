# PSL answers to the frontend connection questions

PSL confirmed these answers on 23 November 2026. The numbers match the developer’s thirteen priority questions. The five follow-up decisions are included in questions 1, 11 and 12. The original questions retain their screen IDs. [Frontend developer’s questions](backend-questions.md)

## Screen-by-screen audit

The screen-by-screen sheet pairs all 224 original questions with their answers under the original IDs. It flags agreed behavior that needs a backend change relative to API 1.24.0. [Backend Answers](backend-answers.md)

## 1. Proof and attachments

**PSL’s answer.** The current PMO Lead can approve a step that belongs to them directly. Their signed-in approval is the record of that decision. Show **Approved by PMO Lead**, the approver’s name and the time. A separate written note or duplicate signature from the PMO Lead is optional. Other staff attach a copy of the signed PDF where proof is required. The agent identifies the attachment for review. Client signatures, Finance approvals and other independent decisions continue through their own steps.

**Backend.** Upload the file to the project, then use the exact action’s upload field or proof endpoint. Milestone completion, project action updates, bid assignment and outcomes, go-live proof and release observations accept checked files through their own routes. The general work proof route retains attachments for work history and delivery observations. An eligible current PMO Lead can approve their named Planning exit directly. The record identifies the PMO Lead and time, and the other required decisions keep their own rules.

## 2. Work progress

**PSL’s answer.** The API should report the current step, what the agent has done, approvals and what was sent. Staff should see those facts on screen.

**Backend.** Work detail supplies `tracking_url` with the current station, intake and verification times, recorded actors, worker activity, output and paginated worker, decision and evidence history. Invoice work uses the original draft, review and delivery receipt. Controlled publications use the exact approved version and recipient receipts. Specialist checks remain in their linked panels. A field stays empty where the source did not record it.

## 3. What a work screen shows

**PSL’s answer.** Give the next person enough information to understand the item and let them click through for the details. PSL asked for a proposed standard.

**Proposed standard.** Show the reference and project, current step, responsible person or role, why the item is waiting, and the next action. The details show the original source, recorded decisions, agent activity and verified receipt where available. Use the current actor’s permitted actions from the backend. Each line can show additional fields that belong to its work.

**Backend.** Work detail includes the common fields and gives each panel its `contract_path` in OpenAPI. Use the schema for that path and the typed command request for each action. Forecast results, BU results and project tab rows already have typed shapes on main. Some line panels still need richer information or exact choices for their current records.

## 4. Company Setup

**PSL’s answer.** An Admin manages settings across the company. Company-wide settings should be accessible from Setup without needing to know a project first.

**Backend.** `GET /setup/scopes` lists the companies and company policies the signed-in Admin can access, with links to their exact authority workspaces. Use those links to create, review, activate and apply company policy versions under the existing grants. Independent business decisions retain their own authority checks.

## 5. Totals and page size

**PSL’s answer.** Show accurate totals. The frontend can decide the page sizes to offer. PSL mentioned 10 or 15.

**Backend.** The work queue accepts `limit=8|10|15|20|50`. `GET /work/counts` returns the authorised queue and line figures with their coverage. A null total indicates an incomplete count. Staff pages give exact authorised totals for accounts and invitations separately.

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

**Backend.** Use the invoice-linked **Record payment** flow at `GET/POST /projects/{case_id}/invoices/{issue_id}/payments`. The backend requires a positive known amount, the payment source, the transaction reference and original evidence before it records a new receipt. Earlier incomplete entries retain their correction path. Finance verifies and allocates payments separately. The Payments read includes verified receipts for the month with the authorised scope and coverage.

## 12. Designed features that need backend data

**PSL’s answer.** Provide a backend for the agreed features. The follow-up decisions below define how staff use images, report notes and alerts.

- **Tola’s notes and findings.** Use the recorded work activity and evidence links. Detailed, authorised agent notes on individual work lines still need line-specific mappings.
- **Report notes and comparison.** Weekly report reviews return the agent’s notes beside their sections for authorised draft reviewers. The approved copy goes out without those review notes. The compare endpoint gives section changes and evidence from authorised versions of the same standalone report and audience.
- **Alerts.** The in-app inbox exposes typed links, unread totals, pages and a daily summary. Email and WhatsApp remain deferred.
- **Assistant images.** Staff can attach private images to questions for Tola, Chidi or Zainab. The backend sends them to OpenRouter with the question and context the person is authorised to use. The adapter test observed the combined request using a test response.
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

The five follow-up decisions have backend answers. The frontend uses the versioned contract and links from each exact record.

| Frontend flow | Expected behavior | Backend status |
| --- | --- | --- |
| Ask an assistant with an image | Attach the image and show the answer with its permitted project sources. | The message links the private images and sends them with permitted context through OpenRouter. |
| Review a report | See the agent’s notes beside each section during staff review. | The weekly report draft read supplies the review notes and the controlled version comparison. |
| Check daily alerts | Open a summary inside the app and follow the original alerts. | The personal inbox returns the summary and typed destinations. |
| Approve a PMO step | Let the eligible current PMO Lead approve their own step. | Planning exit records their role, name and time. |
| Record a payment | Require the real amount and payment source. | The invoice-linked receipt intake enforces both and retains legacy corrections. |

Backend changes are on GitHub `main`. The OpenAPI 1.24.0 snapshot matches production and design acceptance. The in-app browser confirmed the production API version and retired login response. Next.js connection and a live OpenRouter image check remain to be run. [Production API](https://psl-web-production.up.railway.app/api/v1/openapi.json) · [OpenAPI snapshot](../../contracts/psl-factory.openapi.json) · [Test ledger](../../BUILD-TESTS.md)
