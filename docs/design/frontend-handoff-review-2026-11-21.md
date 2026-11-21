# What remains from the frontend handoff

## Decision 2 · Bid sharing

PSL chose privacy at the level of the original bid. The owner can keep it private or make it available to other PMO teams, including its recorded client conversation. Tola can cite the original from a receiving team's own workspace. The owner can withdraw that access. This replaces the earlier proposal below to pick one answer and receiving project. [Decision and browser evidence](bid-sharing-checks-2026-11-21.md)

## Decision 1 · Department assistants

PSL chose role-based access for Tola, Chidi and Zainab on 21 November. For staff on the new roles, the department and project assignment determine what the assistant reads. The single PMO head can ask Tola across PMO, and the Finance head can ask Chidi across Finance. Project staff see their assigned projects. Zainab is available to HR with the live HR connection pending. The earlier references below to project-by-project assistant approval describe the previous setup. [Current role rules](../../guide/11-FULL-PRODUCT.md#role-based-work-and-supervision)

## Repairs and new browser checks · 21 November 2026

The original design work is in [d935c921](https://github.com/stanleykosi/psl-factory/commit/d935c921). The frontend developer added the [backend handoff and its 45 questions in 24d53631](https://github.com/stanleykosi/psl-factory/commit/24d53631). The findings below this update describe the build before the repairs.

The final in-app check used the newer combined My work release. In the live PMO Lead session, **My work and decisions → Decisions** loaded page 1 and correctly showed an empty queue. Railway reported success for web `87c5fc26-446c-45e1-8aec-36ca90868c4a` and worker `02f03744-62d1-420b-a150-7c871cb16c02`. The separate frontend also claimed and approved a second sample invoice through Django after its exact frontend address was configured. The merged role and handoff regression run passed all 37 checks. [Live PMO Lead queue](../test-evidence/handoff-2026-11-21/railway-final-work-desk.jpg) · [Approval through the separate frontend](../test-evidence/handoff-2026-11-21/next-sample-decision.png)

| Where checked | What the browser showed | Evidence |
| --- | --- | --- |
| Railway, Codex in-app browser | Signed in as PMO Lead in **PSL Role Testing**. Opened **My work and decisions**, saw the permitted **Role assignments** link and returned to the PMO dashboard. Both assignment and decision queues were empty. | [Work desk](../test-evidence/handoff-2026-11-21/railway-work-desk.jpg) · [PMO dashboard](../test-evidence/handoff-2026-11-21/railway-pmo-role.jpg) |
| Local Chrome, actual Finance services and PostgreSQL | Opened a sample invoice from My work, claimed the review, chose the review evidence, gave a reason and approved it. The decision appeared in history. The separate Next frontend also opened that exact work item and read the approval from Django. | [Recorded decision](../test-evidence/handoff-2026-11-21/sample-invoice-decision.png) · [History in the separate frontend](../test-evidence/handoff-2026-11-21/next-live-decision-history.png) |
| Local Chrome, two sample bids | The new bid's PM selected a released answer from **SAMPLE-APPROVED-WIN**, saw the original bid cited on the review screen, and accepted the answer for the new requirement. The service test also denied access after release was revoked. | [Winning answer awaiting PM review](../test-evidence/handoff-2026-11-21/winning-answer.png) |
| Local Chrome, sample payroll report | An acknowledged recipient asked Zainab for the approved total. The reply showed 250.00 in the sample currency. The answer came directly from the reviewed report inside the factory. | [Recipient’s answer](../test-evidence/handoff-2026-11-21/approved-payroll-total.png) |
| Local Chrome, sample Finance file | Rechecked an import declared in millions after a matching Finance rule was approved. The original sales amount of −1,000 mapped to −1,000,000,000 NGN. The PostgreSQL test also covered thousands, retrying the same receipt, keeping the original file and holding a new calculation after revocation. | [Calculated figures](../test-evidence/handoff-2026-11-21/converted-millions.png) · [Rule setup](../test-evidence/handoff-2026-11-21/conversion-settings.png) |

The screen checklist now points SCR-25 to weekly reporting and SCR-42 to Planning. Tests also exercised a standalone report approval, retrieval of the recipient-facing preview and replay of a replacement template upload. The checked API has 64 operations across 54 paths. Specialist source selections and several detailed workflows still open their existing factory forms.

**Remaining decisions for PSL.** The payroll owner chooses which aggregate figures an acknowledged recipient may see. Finance identifies the feed, entity, month, currency and permitted file scale. Additional HR data for name and employment checks needs an approved source. Microphone input and actual email or WhatsApp destinations remain open. The browser examples used sample data.

Web release `5bdf9f91-f8d5-4859-93ec-45c33d512c58` and worker release `c0e9a5d3-7151-4c90-bde6-912db6eb6b65` both succeeded on the Railway design-acceptance instance. Its health page returned `ok`. The previously recorded 262 walkthroughs used the former preview database. The current clean workspace received no business transactions from these tests.

## Original handoff review

Reviewed 21 November 2026. The Railway record covers 262 completed walkthroughs across 59 screens. The frontend team also built a separate set of screens against a test server. Several requests from their handoff have since been delivered in the Railway app. Others still affect what staff can do, or what the separate screens can do when connected to real records. [Frontend handoff at the reviewed revision](https://github.com/stanleykosi/psl-factory/blob/16e7bad8788dc0a3fd94e22b13eb6efe5a9ce9f8/delivery/BACKEND-HANDOFF.md) · [Browser evidence](screen-state-acceptance.md)

## Gaps in the factory staff can use

| Area | What works today | What remains |
| --- | --- | --- |
| Department assistants | Tola, Chidi and Zainab answered questions from permitted records in the sample projects. A real model was used in recorded walkthroughs. | The shared project selector explicitly returns only projects marked as test data. An ordinary customer project cannot use this department chat path, even when the staff member has the usual permissions. Real-project use needs an approved source and provider path. [Project selector](../../apps/agents/assistant.py) · [Browser evidence, SCR-05-thread](screen-state-acceptance.md) |
| Answers for new bids | Tola drafts from the current bid requirement. The project manager can accept, edit or replace the answer, and it can go through review and submission. | The handoff asks Tola to find an approved answer from an earlier **winning** bid and show its source. The current draft reads evidence from this bid's project and requirement. The browser ledger explicitly leaves winning-answer reuse open. [Handoff item G-26-5](../../delivery/backend-handoff/gaps-b-rfp-planning.md) · [Answer source](../../apps/pmo/rfp_answers.py) · [SCR-26-edit evidence](screen-state-acceptance.md) |
| Finance files with amounts in thousands or millions | Finance can identify the unit, save evidence and retain the original file. Individual currency units can proceed. | For management accounts, declaring thousands or millions still holds the calculation. The code marks those units unsupported. Turning such a file into figures requires a reviewed conversion path. [Handoff item G-53-2](../../delivery/backend-handoff/gaps-f-finance-workspaces.md) · [Unit check](../../apps/finance/source_units.py) · [Tests defining the hold](../../tests/test_factory_accounting_intake.py) |
| Payroll questions | A person who received a report can open their permitted totals, ask HR a listed question, or ask Zainab about the report's coverage. A private comparison also raised a name discrepancy and a payment after departure in the browser. | Zainab's recipient view supplies the report's coverage and a link to open its figures. Questions are limited to three listed topics. Wider use of approved totals in chat and additional authorised HR sources for names and employment remain follow-ups. [Listed questions](../../adapters/payroll_questions.py) · [Assistant source selection](../../apps/agents/assistant.py) · [Build record](../../BUILD-STATE.md) |

The handoff also proposed speaking a request into the Assistant. It records microphone use as a PSL decision. The email and WhatsApp walkthroughs verified delivery to sample inboxes. Real addresses, numbers and delivery through approved channels still need separate evidence. These are distinct from the verified in-app receipts. [Speech decision G-SCR05-8](../../delivery/backend-handoff/gaps-a-project-setup.md) · [Alert evidence, SCR-15-email and SCR-15-whatsapp](screen-state-acceptance.md)

## Where the separate frontend would break

The coordinator named **My work → open a work item → make a decision** as the first connection to finish. Comparing the frontend on main with the server revealed breaks even where both use the same web address. [Coordinator's list](https://github.com/stanleykosi/psl-factory/blob/16e7bad8788dc0a3fd94e22b13eb6efe5a9ce9f8/delivery/COORDINATOR-HANDOFF.md#L170)

| Staff action | What still needs connecting |
| --- | --- |
| Open the app after signing in | The new menu expects a list of section names. The server sends each section with its name, title and link. The menu's lookup finds no matching sections with that reply. The new navigation also reads a role list absent from this reply. The existing Django sign-in and role desk already work. [Frontend menu](https://github.com/stanleykosi/psl-factory/blob/16e7bad8788dc0a3fd94e22b13eb6efe5a9ce9f8/frontend/src/shell/destinations.ts#L17) · [Server reply](../../apps/core/factory_api/workspaces.py) |
| See the next page of My work or inspect history | The new queue looks for a continuation token. The server gives it the next page number. The server's work-history read returns up to 30 worker events. The handoff also asks for decision and evidence history filters. [Frontend queue](https://github.com/stanleykosi/psl-factory/blob/16e7bad8788dc0a3fd94e22b13eb6efe5a9ce9f8/frontend/src/features/my-work/MyWork.tsx#L119) · [Server queue and history](../../apps/core/factory_api/work.py) |
| Start work | The new form treats only a 201 reply as success. The server creates the work and replies 200 with its ID. Even if a valid request reaches the server, the new form treats that success as uncertain. Several lines also need their source selections connected. [Frontend success check](https://github.com/stanleykosi/psl-factory/blob/16e7bad8788dc0a3fd94e22b13eb6efe5a9ce9f8/frontend/src/features/start-work/useStartWork.ts#L403) · [Server intake test](../../tests/test_factory_api.py) |
| Approve or return a Finance review | The new form submits the decision and optionally a note. The server also requires the ID of the evidence reviewed. A sample approval with the revision, verdict and note passed the frontend specification and failed server validation for that missing ID. The existing Finance review supplies it. [Frontend approval form](https://github.com/stanleykosi/psl-factory/blob/16e7bad8788dc0a3fd94e22b13eb6efe5a9ce9f8/frontend/src/features/decide/useDecision.ts#L192) · [Server decision](../../apps/core/factory_api/work.py) |
| Review a standalone document or upload a replacement template | The Railway app already supports both. The browser approved one exact statement-of-work version, returned another, and uploaded PDF and Word template versions. These two screen groups still have no dedicated JSON operation listed for the new screens. [SCR-08 and SCR-34 evidence](screen-state-acceptance.md) · [Screen connection map](../../contracts/factory-api-screen-map.json) |

Other groups still point staff back to the original forms for specific steps. These include choosing original files and eligible people, recording signers and release evidence, verifying and allocating a payment, correcting private payroll rows, changing Setup rules and checking a recipient's delivery. A generic work read or an approval button establishes only part of each journey. [Per-screen remaining work](../../contracts/factory-api-screen-map.json) · [Connection guide](frontend-api.md)

## Two errors in the screen connection map

| Screen | Approved design and browser record | What the connection map says |
| --- | --- | --- |
| SCR-25 | Write, review and deliver the weekly client update | Bid requirements and reviewed answers. Its listed page opens bid answers. |
| SCR-42 | Collect department inputs, check Planning readiness and hand over to Delivery | Release prerequisites, release observations and the deployment log. Its listed page opens Delivery. |

The map checker confirms that all 262 IDs exist and that each listed technical route exists. It accepts both errors because the wrong routes still exist. The underlying weekly-update and Planning browser records remain valid. [Design inventory](../../design/screens.md) · [Connection map](../../contracts/factory-api-screen-map.json) · [What the checker verifies](../../apps/core/management/commands/export_factory_api.py)

## Work the earlier handoff listed that now has browser evidence

| Handoff area | Example of an actual outcome in the existing app |
| --- | --- |
| Project and Setup | Staff sign-in and invitations were exercised. Template 189 became version 2 while the earlier source stayed visible. See SCR-17, SCR-21 and SCR-34. |
| Bids and Planning | Reviewed requirement answers reached a winning submission. Five departments supplied separate Planning inputs, including a correction from unknown to a known zero. See SCR-26 and SCR-42. |
| Client reports and minutes | A returned weekly report kept the reviewer's reason and went through fresh review. Minutes recovered the original receipt after a delayed reply. See SCR-25 and SCR-28. |
| Delivery | Go-live kept the two signature records. A project milestone was completed with separate proof and handed to Finance. Archive recovery retried just the missing file. See SCR-45, SCR-19 and SCR-47. |
| Payments and payroll | Finance verified a bank receipt and allocated it separately. A payment exception left the debt owed. A payroll recipient acknowledged the corrected report and could still see the earlier withdrawal. See SCR-20, SCR-03-payment-exception and SCR-59. |
| Finance reports | An accounting report recovered its original delivery receipt. Business-unit totals reached final verification after the required recipients acknowledged them. See SCR-53 and SCR-57. |

Each example is traceable by screen ID and sample record in the [Railway browser ledger](screen-state-acceptance.md). The named approvers, financial rules, payroll disclosures and real delivery destinations for a live business operation remain choices for PSL. [Policy configuration guide](../../guide/10-POLICY-CONFIGURATION.md)

## The handoff's ten priorities

| Original request | Current position |
| --- | --- |
| 1. Safe writes and retries | The Finance service checks the reviewer, revision and evidence. Minutes and accounting recovered original delivery receipts in the tested cases. The new frontend still needs the correct start reply, decision payload and recovery details for each action it offers. [Finance API tests](../../tests/test_factory_api.py) · [Browser ledger](screen-state-acceptance.md) |
| 2. Reopen a draft with the saved values | The weekly report reopened with its saved text, period and reference. The new frontend's general-purpose edit-step call has no matching operation in the server export. [Weekly evidence, SCR-25](screen-state-acceptance.md) · [Registered operations](../../apps/core/factory_api/urls.py) |
| 3. Offer only the decisions allowed at this step | Payment exceptions, emergency decisions and reviewed costing have native desks and browser evidence. The new frontend still needs to select the correct desk and send the required evidence. [Decision screens, SCR-03](screen-state-acceptance.md) · [Decision routing](frontend-api.md) |
| 4. Open the right related record | Some server replies already include working links to the original pages. The map still lists project-specific Assistant context and detailed output and receipt links as remaining. [SCR-07 and SCR-14](../../contracts/factory-api-screen-map.json) |
| 5. Record a decision made by someone outside the app | Go-live recorded separate customer and project-manager signature evidence. The new screens still need the controls for signing on someone else's behalf with proof. [SCR-45 evidence](screen-state-acceptance.md) · [Signature and response map](../../contracts/factory-api-screen-map.json) |
| 6. Check one uncertain delivery or file | Archive recovered one missing file and payroll kept each recipient's receipt. The general recovery request takes a work item and action. It cannot express an individual recipient chosen on the new screen. [Recovery handler](../../apps/core/factory_api/work.py) · [Archive and payroll evidence](screen-state-acceptance.md) |
| 7. Deliver internal reports and retain receipts | Accounting, forecasts, payroll and business-unit reports have native delivery or receipt evidence. Their source selection, publication and recipient details still vary by screen. Operational recipients and delivery channels need PSL confirmation. [Finance evidence](screen-state-acceptance.md) · [Finance connections](../../contracts/factory-api-screen-map.json) |
| 8. Choose people and sources for this exact work item | Native pages already select scoped sources and reviewers. The new form's general source-and-person picker has no matching operation at its proposed address. Each form needs the correct native choices. [Server operations](../../apps/core/factory_api/urls.py) · [Intake](../../apps/core/factory_api/intake.py) |
| 9. Show what is known when some money is unknown | The milestone screen kept the signed amount and payment while marking the added price unknown. Month-end distinguished an unrecorded cash balance from zero. The new month-end view expects a combined view across workspaces. The server read is for one workspace at a time. [SCR-36 and SCR-38 evidence](screen-state-acceptance.md) · [Month-end read](../../apps/core/factory_api/workspaces.py) |
| 10. Add missing business records and actions | The earlier list included milestone completion, document review, payroll intake and correction, bid intake, minutes actions, post-launch monitoring and closure. All have native browser examples. The remaining connection work should reuse those records and services. [Screen evidence](screen-state-acceptance.md) · [Connection guide](frontend-api.md) |

## Checks performed for this review

- Read the full frontend handoff on main through its 20 November additions, its 45-question list and its six subject-area gap files. Compared them with the current build, its screen map and the Railway ledger. The two branches reviewed were frontend `16e7bad8` and build `676c6d67`, with local changes present.
- Ran `scripts/design_acceptance_batch.py --audit`. It found 262 recorded completions, zero open and zero unseen. Ran `manage.py export_factory_api --screen-map`. It validated 59 screen groups and 262 states.
- Compared the frontend's 51 proposed operations with the 61 operations in the local server export. **22** shared the same action and address pattern after ignoring the names of record IDs. A different address can serve an existing feature. A shared address can still return data the screen cannot use.
- Compared the two validation rules for a Finance approval and traced the sign-in, queue and work-start replies through the frontend code. The browser evidence cited above comes from the earlier Railway sessions. This review ran local checks and made no new transactions.
