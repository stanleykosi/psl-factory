# Assign the accountable PM: a PMO Lead picks the PM for an unassigned RFP from the backend's list, in a panel over My work (contract mock only)

> Tasks: FE-RFP-INTAKE, part 1 only (R-START; acceptance A-ASSIGN and the Unassigned part of A-START-INTAKE; F-30 assign, F-02 My work and F-09 proof tests kept green). Part 2 (SCR-23, Log a received RFP) is held until F-47 merges evidence intake. Architecture: package `architecture/packages/v7`, manifest digest `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624`; FE-RFP-INTAKE at `architecture/packages/v7/delivery.md:1843-1875`, `gate_ids: []`, "Unresolved gates: none"; E-WORK-ASSIGN's trigger is "Assign drawer from the Unassigned queue (SCR-24)" (`model.json:14592`); A-ASSIGN at `model.json:20180-20193`. Typed today: `assign {role, candidates[], note_required}` and `rfp` on E-WORK-ITEM (`frontend/src/api/schema.d.ts:1664`, `:1900`), E-WORK-ASSIGN (`:5329`), E-WORK-LIST `queue=unassigned`, E-EVIDENCE-UPLOAD. This feature changes no generated type. Decision consumed: D-RFP-INTAKE r1 (`proposed`, backend developer). Proposals on a mock overlay only: G-24-1, G-24-2, G-24-3 (`delivery/backend-handoff/gaps-b-rfp-planning.md:36-52`). Design: client-approved canvas version 1794581312-b166 (13 Nov 2026), republished with "+ Start" as 1794762832-cab1 (D-89). `design.py check --project .` was run for this spec on 18 Nov: `EXCEPTION`, `passes: true` (design_sha256 `2859ab21…3d82`, D-89 frame-only change). Screens: SCR-24, 2 artboards: `design/canvas/project/SCR-24-desktop.dc.html` (a 500px dialog over My work's Unassigned tab) and `SCR-24-mobile.dc.html` (a sheet over My work). Models: `delivery/features/F-30/spec.md` (`AssignForm`, `useWorkspaceAssign`, the E-WORK-ASSIGN mock), `F-09/spec.md` (`ProofField`, `useEvidenceUpload`), `F-31/spec.md` (the F-30 form lifted, notice only after the re-read, 44px chip remove). Decisions reused: D-64, D-83, D-89, D-91, D-92c, D-92d (one 500px Drawer), D-104, D-111 to D-113.

## Conflicts with the boards (for the design engineer, before the build)

"Recommend" is what this spec builds if no answer comes. Each difference becomes an entry in `delivery/features/F-36/fidelity-exceptions.json` with `approved_by: "builder proposal, pending design engineer"` until it is signed. Items 1 to 6 change what a person sees or can do, and need an answer. Items 7 to 9 are layout. Items 10 to 12 are exceptions to sign.

### Need an answer

1. **Where the panel opens.** Both boards draw the panel over the My work list (Unassigned tab), and the architecture names it "Assign drawer from the Unassigned queue". The readiness note says "over the work item". **Recommend:** follow the boards. Pressing an RFP row on the Unassigned tab opens the shared `Drawer` "Assign accountable PM" over the list, at `/my-work?queue=unassigned&assign=<work_id>`. The list stays behind it. After assigning, the row leaves the list. If the item turns out to carry no `assign`, the page goes to `/work/<id>` as today, so Unassigned rows for other kinds of work behave as before. **Option B:** the panel sits on the work item page `/work/<id>`. The list is not drawn behind it, the score is lower, and a D-83 waiver is needed.
2. **Nobody is chosen for you.** The board shows "Tunde Bello · PMO" already chosen. **Recommend:** the list starts empty ("Choose a PM"), and the person picks from `assign.candidates` only. Each choice shows the name with the role and load hint as returned. Choosing someone ahead of time would record a choice the person did not make, and v7 has no "suggested PM" field. **Option B:** pre-choose only when the backend names a default (F-31's `default_person_id`, G-41-1). That would add a fourth proposal, so it is not built here.
3. **"You are assigning as".** Today the contract sends one role and the request has no role (G-24-1). **Recommend:** with a single role, show it as plain text ("PMO Lead") with the help line "One of the roles PSL allows to assign RFPs", and send no role. Only when the response lists more than one role (overlay `assign.roles[]`) show a drop-down of exactly those roles. The backend's default (`assign.role`) is chosen, and the chosen role is sent as `acting_role`. Nothing comes from the signed-in person's roles. The board's "▾" on a single role becomes a listed difference.
4. **Proof (optional).** The contract has no proof on an assignment, and an upload needs the RFP's case (G-24-2, G-23-5). **Recommend:** the Proof field appears only when the response carries `assign.evidence_kind` (overlay). It takes one file, uploaded when chosen. "Assign PM" waits while it uploads. A file that failed or could not be confirmed is never sent: the person retries or removes it first. Without the overlay there is no Proof field, which is a listed difference on the board fixture's typed twin. Proof shows on the phone too when the response offers it, although the phone board does not draw it.
5. **"What happens next".** The board promises "Tunde is alerted by WhatsApp and email … and Tola investigates it straight away". **Recommend:** with the overlay `assign.next`, show the backend's `summary` and `agent` sentences exactly as returned. The page names no channel the response does not name. Without the overlay, show fixed wording that names no channel and makes no claim about Tola: "The PM you choose is alerted and sees it in Needs me. They start the RFP response." The backend cannot know the chosen name before the choice, so "Tunde" in the board's sentence is sample data. No analysis job exists yet (G-24-4), so the backend should not send the Tola sentence until one does. Its wording is a product acceptance check.
6. **Who is signed in on the sample.** The board's assigner is "Kemi Adebayo · PMO Lead". In the mock, no one but the Finance Lead can see Unassigned, and persona `pm` is Tunde Bello, the PM being assigned. **Recommend:** a mock-only persona `pmo_lead` (Kemi Adebayo, roles ["PMO Lead"]) who sees the Unassigned queue. The page never reads roles; the persona only decides which sample list the mock serves. **Option B:** let persona `ceo` see Unassigned. The sign-in name then differs from the board, and the CEO's My work counts change.

### Layout

7. **The phone shows the desktop's content.** The phone board leaves out the intro sentence, "3 people can prepare RFPs here", the role help line and Cancel, and shortens "Next". **Recommend:** the phone sheet shows the same lines and fields as desktop in one column (D-111, F-30 conflict 5), with "Assign PM" full width and pinned at the bottom. As on the phone board, there is no Cancel; the sheet's "×" closes it. Desktop keeps Cancel, "Assign PM" and "×", as drawn.
8. **The list behind the panel is My work as built.** The board's row has no kind tag and only three columns (WORK, STATE, AGE), with the meta "RFP received · TL-RFP-2026-014 · deadline 28 Nov" and the tag "NEEDS A PM". **Recommend:** keep My work as built (F-02, D-17, D-20): the kind tag, four columns, the meta from `line · reference` (no deadline in a list row), and the state word "Owner needed" from the contract. These are listed as `page behind`.
9. **Phone bar "← My work".** My work is a top-level page and has no back link; the sheet covers the bar. **Recommend:** no frame change; the sheet's "×" returns to the list (`frame item`).

### Exceptions to sign

10. **Sample values.** The chosen PM, the file name and size ("assignment-email.eml · 18 KB") and the note text ("Tunde led the Lagoon Health bid…", phone "Led a similar bid") are drawn filled in on the boards. The page starts empty (`sample data`).
11. **Words that come from data.** The drawer heading "TAMARIND LOANS · TL-RFP-2026-014" is the desktop eyebrow; on the phone it is the subline "Tamarind Loans · TL-RFP-2026-014". Both come from `rfp.client · rfp.reference`, not typed into the code. "3 people can prepare RFPs here" counts `assign.candidates`.
12. **Visual waivers.** If a board scores under 90 visual after these exceptions, it gets a board-level waiver citing D-83 (floor 70) and items 7 to 9. The design engineer signs each one.

## Boards

| Board | File (`design/canvas/project/`) | Page | Mock cookies |
|---|---|---|---|
| SCR-24 desktop | `SCR-24-desktop.dc.html` | `/my-work?queue=unassigned&assign=W-3302` at 1440 | `psl_mock_persona=pmo_lead`, `psl_mock_worklist=board` |
| SCR-24 phone | `SCR-24-mobile.dc.html` | same URL at 390 | same |

Both are live URLs. The state after assigning, the errors and the uncertain case are not boards.

## Summary
- A PMO Lead on My work → Unassigned presses the logged RFP. The 500px Drawer "Assign accountable PM" (a phone sheet) shows which client and RFP it is, the PMs the backend lists (name, role, load hint, "n people can prepare RFPs here"), the role they assign as, optional proof, a note and "What happens next". "Assign PM" sends one E-WORK-ASSIGN.
- Authority comes only from the response. No `assign` block means no control. Candidates and roles are exactly what is returned. Nothing is chosen ahead of the person, and nothing comes from `/me`. 403 and 404 look the same.
- The success words appear only after the item and the list are re-read. A failed, timed-out or uncertain write never says "assigned". The page re-reads first, and offers the form again only if the re-read still carries `assign`.
- G-24-1 (roles and `acting_role`), G-24-2 (`evidence_id`, `assign.evidence_kind`) and G-24-3 (`assign.next`) are built on a mock overlay only. Without them, the page sends exactly the typed body.
- It reuses F-30's `AssignForm` and `useWorkspaceAssign`, lifted so they work on an item that has no line workspace, plus F-09's `ProofField` and `useEvidenceUpload`, the shared `Drawer` and the My work Unassigned tab. Contract mock only; nothing is sent to anyone.

## Context
- **My work:** `frontend/src/features/my-work/MyWork.tsx` (view from the URL with `parseView`/`viewSearch` in `model.ts:85-113`; `load` and `refresh` re-read page 1; 15-second poll), `WorkRows.tsx` (`WorkTable` and `WorkCards` link every row to `/work/<id>`), `model.ts:27` (the Unassigned queue). The mock `frontend/mock/work-list.mjs:21` treats only `finance_lead` as a Lead; other personas except `none` get 403 `queue_not_open` on `unassigned`.
- **Assign form (F-30, being lifted by F-31):** `frontend/src/features/workspace/AssignForm.tsx` (Select of `assign.candidates`, no preselection, Note, 2000-character limit, Escape closes) and `useWorkspaceAssign.ts` (`ASSIGN_TEXT`, one write at a time, 409 → re-read, 5xx or network → "Not recorded" and re-read, no resend). It takes `revision` and a `WorkspacePage` (`usePageReload.ts`: `reload`, `refreshFailed`, `onAccessLost`). Workspace passes `workspace.revision`; an RFP item without a workspace uses the item's `revision`. **Today `done` is set before `page.reload()`** (`useWorkspaceAssign.ts:62-64`). This feature moves it after the re-read, as F-31 round 2 did for its own notice. F-31 (`/Users/Hunchoo/psl-factory-worktrees/f-31`, in QA) already adds `preset`, `labelledBy`, an optional `onClose`, `role` and the `pm*` words to these two files. Build on F-31's version.
- **Proof (F-09):** `frontend/src/features/response/ProofField.tsx` (layouts `drop`, `phone` and `card`; `label`, `choose`; chip remove "×" is 24px in `response.css:77`) and `useEvidenceUpload.ts` (needs `caseId`, `caseRevision`, `kind`, `reloadCaseRevision`, `onAccessError`; one upload at a time; Try again re-reads first). F-31 round 3 raised the chip remove to `--control-phone` inside its panel (`workspace.css:252` in the F-31 worktree). This Drawer needs the same.
- **Shared library (D-91):** `Drawer` (`eyebrow` on desktop, `subline`, `footer`, `initialFocus`), `Select`, `TextArea`, `Button`, `Callout`, `ValidationSummary`, `Unknown`, `Tag`. No local copy of anything `@/components` exports.
- **Work item read:** `useWorkItem`, E-WORK-ITEM via `mock/server.mjs` `workResponse` from `mock/fixtures/work/<id>.json`. `case_id` and `case_revision` are on the item (`schema.d.ts:1539`).
- **Mock writes:** `frontend/mock/workspace.mjs` `handleAssign` checks scenario, CSRF, 404, the typed body (`additionalProperties: false`), a `person_id` among the candidates, the `psl_mock_assign` cookie, then `expected_revision` against `current.workspace?.revision`. It also clones `workspace` on `stale`. An item without a workspace would always get 409; this is fixed below. Uploads to work-item cases are in `mock/response.mjs:108` (`upload`: kinds and grant from tasks, reconcile and rfp_outcome only).
- **Sample world:** client Tamarind Loans exists (`CL-3506`, `mock/fixtures/clients/list.json:57`). The same RFP reference TL-RFP-2026-014 appears later in its life on W-2112 (F-18, PM Tunde Bello).
- **Tests that must stay green:** `tests/issue-detail.test.tsx`, `tests/issue-assign-mock.test.ts`, `tests/workspace.test.tsx`, `tests/my-work.test.tsx`, `tests/my-work-model.test.ts`, `tests/mock-work-list.test.ts`, `tests/response.test.tsx`, `tests/response-mock.test.ts`, `tests/mock-contract.test.ts` (one expected row added for the new persona, nothing else), F-31's tests once merged, and the e2e `my-work.spec.ts`, `issue-detail.spec.ts`, `response.spec.ts`.

## Contract

### Reads
- **E-WORK-LIST `GET /api/v1/work?queue=unassigned`** (unchanged). Persona `pmo_lead` gets the W-33xx rows; the other personas behave as today. 403 keeps F-02's "not open" message.
- **E-WORK-ITEM `GET /api/v1/work/{work_id}`** (unchanged). Read when the Drawer opens and again after every write. It uses `title`, `reference`, `revision`, `case_id`, `case_revision`, `rfp.{client, reference, pm}` and `assign`.
  - Loading: the Drawer body shows the shared loading state, and no control is drawn.
  - 401: the signed-out state, with `next=/my-work?queue=unassigned&assign=<id>`.
  - 403 or 404: the same not-open view inside the Drawer ("You can't open this item."), with no client, reference or name, and no further call.
  - 5xx: the problem card with Retry.
  - No `assign` in the response: `router.replace('/work/<id>')`.
  - `assign` with no candidates: "No one can prepare RFPs here yet." and no control.

### What the panel draws, from the response only
| Part | Source | Absent |
|---|---|---|
| Eyebrow / subline | `rfp.client` · `rfp.reference` (falls back to `title` · `reference`) | "Unknown" for a missing part |
| Intro | fixed: "Only people allowed to prepare RFPs for this workspace are listed. Who may assign is set by PSL in Setup." | — |
| Accountable PM | `Select` of `assign.candidates` (label `name`; hint `role · hint` as returned), placeholder "Choose a PM", nothing chosen | no hint → name and role only, never "0" |
| Count | "`n` people can prepare RFPs here" ("1 person can …") from `candidates.length` | — |
| You are assigning as | overlay `assign.roles[]` with more than one entry → `Select` of those labels, `assign.role` chosen when it is one of them, else none; otherwise the text of `roles[0].label` or `assign.role`; help "One of the roles PSL allows to assign RFPs" | no role at all → the row is not drawn |
| Proof (optional) | overlay `assign.evidence_kind` → `ProofField` (`layout="card"`, one file, `kind` = `evidence_kind`, case = item `case_id`/`case_revision`) | not drawn |
| Note | `TextArea`, optional unless `note_required`, 2000 characters | — |
| What happens next | overlay `assign.next.summary` then `assign.next.agent`, as returned | the fixed sentence in conflict 5 |
| Actions | "Assign PM" (primary), "Cancel" (desktop), "×" | — |

The RFP wording ("Assign accountable PM", "Accountable PM", "Choose a PM", "Assign PM") is used when the item carries `rfp`. Any other item keeps F-30's words. This is presentation only; it grants nothing.

### Overlay (mock only; file `frontend/mock/proposals/rfp-assign.json` with a `$comment`; each field goes in build.md for the backend developer)
- `assign.roles: [{role: string, label: string}]` (minItems 1), with `assign.role` kept as the default key. Request: `acting_role` (one of `roles[].role`). G-24-1, blocking for the real write.
- `assign.evidence_kind: string`. Request: `evidence_id` and `case_revision` (the revision the upload returned). G-24-2, blocking.
- `assign.next: {summary: string, agent?: string, channels: ("whatsapp"|"email"|"in_app")[]}`. G-24-3, nice-to-have. `channels` is not drawn on its own; the backend's `summary` words them.
- `assign.role` means the role the assigner acts in (readiness, G-24-1). F-31 reads it as the label of the person being chosen ("PM"). The backend is asked to settle the meaning (build.md). This feature's fixtures send "PMO Lead" and draw it only in "You are assigning as".

### E-WORK-ASSIGN `POST /api/v1/work/{work_id}/assignment`
- **What is sent:**
  - Without the overlay: exactly `{expected_revision: item.revision, person_id, note?}` and the header `X-CSRFToken`. `person_id` is one of `assign.candidates[].person_id`; the note is trimmed and left out when empty.
  - With the overlay: also `acting_role`, only when `assign.roles` is present. `evidence_id` and `case_revision` go only when exactly one file has status `uploaded`.
  - Nothing else is ever added. There is no idempotency key, because the typed body has none.
- **What is held:**
  - No request is sent while an upload is running, while a re-read is running, after a failed re-read (`refreshFailed`), or while another assign is in flight. A double press sends one.
  - A chip that failed or could not be confirmed blocks the send, with "Remove the file that didn't upload, or try it again." It is never sent as attached.
  - After an uncertain result, nothing is sent again until the re-read shows `assign` still present.
- **200 `{work_id, state, revision, assigned_to}`:** re-read the item, then refresh the list (`refresh`). Only then close the Drawer and show the polite notice above the list: "TL-RFP-2026-014 is now with Tunde Bello." (the item's reference and `assigned_to`). Focus goes to the Unassigned tab. If the re-read fails: "The assignment was sent, but we couldn't refresh to confirm it. Reload My work to check." No "assigned" words appear before a re-read.
- **409:** re-read and show the F-30 stale sentence. The choices are kept when the chosen person and role are still returned; otherwise they are cleared with "That person can no longer be chosen." The next press sends the new revision. If the re-read carries no `assign`, the Drawer shows the read-only result (below) and no form.
- **422:** messages under the named fields (`person_id` → Accountable PM, `note`, `acting_role` → You are assigning as, `evidence_id` → Proof), a top summary, focus on the first field, and entries kept.
- **5xx, network or timeout (uncertain):** "Not confirmed: we couldn't confirm the PM was assigned. Check before trying again." Then re-read:
  - `assign` gone → the read-only result "Assigned to `rfp.pm.name`" ("Unknown" when `rfp.pm` is absent) and no form;
  - `assign` still present → the form with entries kept and "Try again".
- **Permission and tenant:** the form exists only when the response carries `assign` with at least one candidate. The page never filters candidates or roles and never reads `/me`. Who may assign is the backend's rule (`presale.rfp_assigner` exists only in the SCR-13 mock fixtures). There is no fallback assigner.

### E-EVIDENCE-UPLOAD `POST /api/v1/cases/{case_id}/evidence` (overlay only)
Through `useEvidenceUpload` unchanged: `{kind: assign.evidence_kind, filename, content_base64, case_revision}` with CSRF. The returned `case_revision` is the one sent on the assign. On 409 or a failure, the chip shows its problem and Try again (re-read first). Removing a file only stops it being sent; the evidence stays on the case.

### Fixtures (all `sample: true`, client Tamarind Loans `CL-3506`, `rfp.reference` TL-RFP-2026-014 unless stated, state `owner_needed`, `revision` 1, own case `C-33xx`, revision 1)
| Id | Purpose | `assign` |
|---|---|---|
| W-3301 | typed only | `role: "PMO Lead"`, 3 candidates (Tunde Bello · PMO · "2 RFPs in progress"; Sola Martins · PMO · "1 RFP in progress"; Ife Okoro · PMO, no hint), `note_required: false` |
| W-3302 | the board (overlay) | as W-3301 plus `roles` [PMO Lead, CEO], `role: "pmo_lead"`, `evidence_kind: "assignment_proof"`, `next` {summary "The PM you choose is alerted by WhatsApp and email and sees it in Needs me. They start the RFP response.", agent "Tola starts reading the RFP once the PM opens it.", channels [whatsapp, email]} |
| W-3303 | one candidate, note required (reference HB-RFP-2026-021, Harmattan Bank) | 1 candidate, `note_required: true` |
| W-3304 | empty list (Kora Logistics) | `candidates: []` |
| W-3305 | no authority (Ojo Foods) | no `assign` → goes to `/work/W-3305` |
| W-3306 | uncertain, written (Sabi Market) | as W-3301; script `W-3306.assign.json` `{status: 500, written: true}` |

W-3301, W-3302, W-3303 and W-3306 have a `.next.json`: `assign` removed, `revision` 2, state `waiting`, `rfp.pm {name: "Tunde Bello", role: "PM"}` (Sola Martins for W-3303). Each fixture validates against the generated E-WORK-ITEM 200 schema once the overlay keys are removed. The overlay keys are type-checked on their own against `rfp-assign.json`, not just deleted (F-31 TECH-1-2). The list rows for `pmo_lead` go in `E-WORK-LIST.rows.json` (queue `unassigned`, line "RFP received", `line_key` `rfp_intake`, kind `do`). `E-WORK-LIST.board.json` gains a `pmo_lead` entry with the board's counts (3, 2, 28, 1) and the single W-3302 row. No T- ids are needed (no tasks).

### Mock behaviour
- `server.mjs`: persona `pmo_lead` in `PERSONAS` with `fixtures/me.pmo_lead.json` (Kemi Adebayo, roles ["PMO Lead"], destinations as `pm`, `csrf_token` "mock-csrf-pmo_lead"). Every per-persona mock answers it schema-valid (alerts map it to `none`, as admin and ceo; `mock-contract.test.ts`'s persona loop passes).
- `work-list.mjs`: `pmo_lead` is a Lead. An Unassigned row whose assignment was written is dropped, and its count goes down by one (read from `workspace.mjs`'s assignment log). `/__mock/reset` restores it.
- `workspace.mjs` `handleAssign`:
  - It compares `expected_revision` and clones on `stale` using `workspace?.revision ?? revision`.
  - It validates against the overlay request schema when the served item carries `assign.roles` or `assign.evidence_kind`, else against the typed schema.
  - 422 for an `acting_role` that is not in `roles`, or an `evidence_id` not uploaded on the item's case. 409 for a `case_revision` that is not current.
  - It reads `<id>.assign.json` (`{status, written}`) as a script after the revision check.
  - The 200 `revision` falls back to the item's.
  - F-30's order, cookies (`psl_mock_assign=stale|invalid|uncertain|uncertain_written`) and log are unchanged.
- `response.mjs` `upload`: `assign.evidence_kind` counts as an accepted kind and as a grant on that item's case.
- Local use only: nothing is sent to anyone.

## Lanes
- **Frontend lane (builder)** owns:
  - New `frontend/src/features/rfp/AssignPmDrawer.tsx` (the Drawer, its read, the panel parts, proof, success and uncertain views).
  - `frontend/src/features/rfp/proposals.ts` (overlay readers `assignRoles`, `assignEvidenceKind`, `assignNext`; malformed → treated as absent), plus additive `rfp.css` rules (tokens only, including `.psl-drawer .resp-chip__remove, .psl-sheet .resp-chip__remove { min-width/min-height: var(--control-phone) }` on phone).
  - Additive props in `features/workspace/AssignForm.tsx` (labels and an extra-fields slot) and `useWorkspaceAssign.ts` (extra body fields; `done` set after the re-read). The F-30 and F-31 call sites draw and send exactly as before.
  - `features/my-work/model.ts` (`assign` in `View`, `parseView`, `viewSearch`), `WorkRows.tsx` (Unassigned rows link to `?queue=unassigned&assign=<id>`), `MyWork.tsx` (mount the Drawer, `refresh` after a write, the notice).
  - The mock files above and fixtures `me.pmo_lead.json`, `work/W-3301..W-3306` (+ `.next.json`, `W-3306.assign.json`), the appended list rows and the board entry, and `proposals/rfp-assign.json`.
  - Tests `frontend/tests/rfp-assign.test.tsx`, `rfp-assign-mock.test.ts`, `mock-contract.test.ts` (the new persona row and fixtures only), and `frontend/e2e/rfp-assign.spec.ts`.
  - Fidelity files in `delivery/features/F-36/`.
- **Shared, read only:** `src/components/**`, `src/shell/**`, `src/api/**` (including `schema.d.ts`), `src/styles/**`, `src/features/start-work/**`, `src/features/response/**` (import `ProofField` and `useEvidenceUpload`; change only if a test proves a defect, and list it), `Workspace.tsx`, `usePageReload.ts`, existing fixtures other than the appended rows, `package.json`, the lock file, the Playwright and Vitest configs, `architecture/**`, `design/**`, `apps/**`, and the protected `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`.
- **Backend lane:** none. For build.md (not blocking this build): G-24-1, G-24-2 (with G-23-5), G-24-3 and G-24-4; the meaning of `assign.role`; the three questions at `gaps-b-rfp-planning.md:49-52` (which Setup rule names assigners and candidates; reassignment; the alert body under I-ALERTS).
- **Integration owner:** the coordinator. F-31 changes `AssignForm.tsx`, `useWorkspaceAssign.ts`, `workspace.mjs` and `workspace.css`, so start this branch from dlv-00 after F-31 merges, or merge it in before building. Whichever of F-36 and any other feature touching `server.mjs` or `work-list.mjs` merges second takes the current base and reruns `delivery/checks.sh` and the e2e.
- **Ports:** app 4960, mock 4961. Run `cd frontend && E2E_PORT=4960 MOCK_PORT=4961 npx playwright test e2e/rfp-assign.spec.ts e2e/my-work.spec.ts e2e/issue-detail.spec.ts e2e/response.spec.ts` with `timezoneId: 'Africa/Lagos'`. Fidelity runs on a production build (`next build`, `next start -p 4960`, mock on 4961), once per round over both boards (D-64). Check `df` first and stop under 3 GB; delete `frontend/test-results` afterwards. The e2e is not in `checks.sh`, so paste its output in build.md.
- **Review routing (medium risk, `auth`):**
  - Technical: Sonnet.
  - UI: the fidelity gate on 2 boards, Opus for the first review.
  - UX: Sonnet.
  - QA: Opus.
  - Security: Opus on this diff (first acting-role authority).
  - Product acceptance is required.
- **Size:** about 700 to 1,000 lines, half of them tests and fixtures. One PR.

## Acceptance criteria

### Panel and authority
1. **Opens over My work.** As `pmo_lead` on `/my-work?queue=unassigned`, pressing "Tamarind Loans · loan origination RFP" opens the Drawer "Assign accountable PM" over the list at `?queue=unassigned&assign=W-3302`. The desktop eyebrow is "TAMARIND LOANS · TL-RFP-2026-014"; the phone subline is "Tamarind Loans · TL-RFP-2026-014". The list stays drawn behind. Escape, "×" and Cancel close it with no request and return focus to the row link. — verify: e2e at 1440 and 390; component test with a recording `fetch`.
2. **Candidates only from the response.** On W-3301 the Accountable PM list holds exactly the three candidates (name, plus role and hint as returned; Ife Okoro shows no hint, not "0"). Nothing is chosen ("Choose a PM"). There is no free-text option. The text reads "3 people can prepare RFPs here"; W-3303 reads "1 person can prepare RFPs here". — verify: `cd frontend && npx vitest run tests/rfp-assign.test.tsx`.
3. **No `assign`, no control.** W-3305 sends the person to `/work/W-3305` with no assign control anywhere. W-3304 shows "No one can prepare RFPs here yet." and no Select or "Assign PM". Removing `assign` from a W-3301 copy draws no control. The code reads no `/me` (`git diff` adds no `/me`, `useMe` or `roles` read under `features/rfp`, `features/my-work` or `features/workspace`). — verify: component tests; grep on the diff.
4. **Acting role from the response only.** W-3301 shows "You are assigning as · PMO Lead" as text and sends no `acting_role`. W-3302 shows a Select of exactly "PMO Lead" and "CEO", with "PMO Lead" chosen (the returned default). Choosing "CEO" sends `acting_role: "ceo"`. The same pages for personas `pm` and `ceo`, given the same item, draw the same role choices (the role does not follow the signed-in person). — verify: component tests with three personas; request bodies.
5. **What happens next.** W-3302 shows the returned `summary` and `agent` sentences word for word. W-3301 shows the fixed sentence, which names no channel and has no "Tola" (`textContent` contains no "WhatsApp", "email" or "Tola"). — verify: component tests.

### Writes
6. **Typed assign.** On W-3301, choosing Tunde Bello and pressing "Assign PM" sends one POST `/api/v1/work/W-3301/assignment` with `X-CSRFToken` and a body that validates against the generated E-WORK-ASSIGN request schema: `{expected_revision: 1, person_id: <Tunde's id>}` plus `note` only when typed (trimmed), and no other key. A double press sends one. — verify: component test; `GET /__mock/workspace-log` `assignments` in `rfp-assign-mock.test.ts`.
7. **No success before the re-read.** On 200, the Drawer stays until the item re-read and the list refresh both finish. Only then the notice "TL-RFP-2026-014 is now with Tunde Bello." appears, the row is gone, and the Unassigned count is one lower. A fake-timer test that holds the re-read shows no "is now with" and no closed Drawer while it is pending. If the re-read fails, the page shows the "sent, but we couldn't refresh" sentence and no success words. — verify: component tests; e2e reads the list after assigning.
8. **Overlay assign with proof.** On W-3302, choosing a file uploads one E-EVIDENCE-UPLOAD with `kind: "assignment_proof"` and `case_revision: 1`. "Assign PM" then sends `acting_role`, `evidence_id` and `case_revision: 2`, and the mock records it. While uploading, Assign sends nothing. With the upload made to fail (`psl_mock_scenario=500` on the upload), the chip shows its problem and Try again; Assign shows "Remove the file that didn't upload, or try it again." and sends nothing. Removing the chip then lets Assign send without `evidence_id`. — verify: component tests; `rfp-assign-mock.test.ts`.
9. **Validation.** Pressing Assign with no PM shows "Choose a PM to continue." under the field, a top summary and focus on the field, and sends nothing. On W-3303, an empty note shows "Add a note to continue." A note over 2000 characters is refused before sending. A mock 422 naming `person_id`, `acting_role` or `evidence_id` puts the message under that field and keeps the entries. — verify: component tests; `psl_mock_assign=invalid`.
10. **Stale.** With `psl_mock_assign=stale`, the 409 re-reads and shows the stale sentence with the choices kept. The next press sends `expected_revision: 2` and succeeds. After 60 seconds of fake time there is still only one POST. — verify: component test; mock log.
11. **Uncertain never says assigned.**
    - W-3306 (written, then 500): "Not confirmed …", then the re-read shows "Assigned to Tunde Bello", no form, and no second POST.
    - `psl_mock_assign=uncertain` on W-3301 (500, nothing written): the re-read shows the form with entries kept and "Try again". Pressing it sends exactly one more POST.
    - A network error behaves as `uncertain`.
    - In none of these cases does "is now with" or "assigned" appear before the re-read.
    — verify: component tests; e2e checks the mock's `assignments` (one written for W-3306, none for `uncertain`).
12. **Access 401, 403, 404.** A 401 on the item read or the write shows the signed-out state with `next` set to the panel URL. A 403 and a 404 (W-3399, which has no fixture) show the same not-open view in the Drawer, with no client, reference or name and no further call. A 403 on the write does the same. Persona `pm` on `?queue=unassigned` keeps F-02's "Only Leads can see unassigned work." — verify: component tests with a recording `fetch`; e2e for `pm`.
13. **Unknown, never 0.** On a copy of W-3301 with `rfp.client`, a candidate's `role` and `hint` and the file size removed, the page shows "Unknown" where a value is drawn (header part, size "Size unknown"), never a blank, "0" or "0 RFPs". After the write, a re-read with no `rfp.pm` shows "Assigned to Unknown". — verify: component test on the modified copy.

### Quality
14. **Phone (D-92c).** At 390 the sheet shows the same parts as desktop in one column (conflict 7), with "Assign PM" pinned and no sideways scroll. Every target in the sheet is at least 44px, including the Select, the role Select, the file button, Try again and **the uploaded file chip's remove "×" after an upload** (the F-31 QA-2-1 lesson). Links inside a sentence are exempt (D-95). — verify: e2e measures `getBoundingClientRect` of every button, link and input in the dialog before and after a W-3302 upload.
15. **Fidelity (D-64).** One design-fidelity run per round over both boards on a production build, with the cookies in the Boards table. Element coverage after approved exceptions is 100% on each board, and visual is at least 90 or carries a board-level waiver citing D-83, never under 70. Every exception has `role`, `name`, `category`, `reason` and `approved_by` and maps to a Conflicts number. None covers a value the data can supply (a name, a reference, a count or a returned sentence). — verify: the fidelity command per board (`--width 1440`, `--width 390`); `round-<N>/fidelity/`.
16. **Accessibility.** No axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`) at 1440 and 390 on W-3301, W-3302 (before and after an upload), W-3304, the 422 state, the uncertain state, the not-open view and the list after success. The Drawer is a labelled dialog with focus held inside it. Every field has a label. Errors and the success notice are announced (`role="status"` or `alert`). Nothing animates under `reducedMotion: 'reduce'`. — verify: `e2e/rfp-assign.spec.ts`.
17. **Tokens and components only.** `git diff` adds no `#hex`, `rgb(` or `hsl(` in any `.css`, and no literal px size outside a token. There is no local copy of a component `@/components` exports; the Drawer, Select, TextArea, Button, Callout and ValidationSummary are the shared ones, and the proof is F-09's `ProofField`. — verify: grep on the diff.
18. **Mock matches the contract.** `rfp-assign-mock.test.ts` checks:
    - Every W-33xx fixture validates against the generated E-WORK-ITEM schema with overlay keys removed, and the overlay keys validate against `proposals/rfp-assign.json`.
    - A typed request with an extra key is a 422; an overlay request is accepted only for an overlay item.
    - An `acting_role` not in `roles` and an `evidence_id` not uploaded are 422.
    - Revision checks work on an item without a workspace.
    - The written assignment drops the Unassigned row.
    - `/__mock/reset` restores everything.
    — verify: `cd frontend && npx vitest run tests/rfp-assign.test.tsx tests/rfp-assign-mock.test.ts tests/mock-contract.test.ts`.
19. **Contract not extended.** `git diff --stat` against the base shows no change in `frontend/src/api/**`, `apps/**`, `architecture/**`, `design/**`, `frontend/src/shell/**`, `frontend/src/features/start-work/**`, the protected paths, or existing fixtures other than the appended `pmo_lead` rows. Every overlay field and request key is listed as a contract proposal in build.md. — verify: `git diff --stat`; build.md.
20. **Existing behaviour green.** F-30 assign, My work and F-09 proof all still pass: `cd frontend && npx vitest run tests/issue-detail.test.tsx tests/issue-assign-mock.test.ts tests/workspace.test.tsx tests/my-work.test.tsx tests/my-work-model.test.ts tests/mock-work-list.test.ts tests/response.test.tsx tests/response-mock.test.ts`, plus `E2E_PORT=4960 MOCK_PORT=4961 npx playwright test e2e/my-work.spec.ts e2e/issue-detail.spec.ts e2e/response.spec.ts`. W-2413 still says "Set an owner" and "Owner set: …". F-31's W-2601 still says "Confirm PM" when merged. Finance Lead's Unassigned receipt rows still end on `/work/W-1137` and `/work/W-1138`. — verify: the commands; build.md output.

## Out of scope
- SCR-23 Log a received RFP (part 2, after F-47), the `rfp_intake` Start work line and any change under `features/start-work/**`.
- Reassigning an RFP that already has a PM, or unassigning one (no board; a backend question).
- The RFP response workspace (SCR-26, F-37), the analysis job JOB-RFP-ANALYSE (G-24-4) and any claim that Tola has started.
- Real alert sending (I-ALERTS), choosing channels, and showing a channel the response does not name.
- A suggested or default PM (`default_person_id`), filtering or sorting candidates in the browser, a typed-in PM, or a team as PM.
- Assigning from the work item page `/work/<id>` (it renders as today).
- Moving the RFP into Tunde's Needs me in the mock (the list mock only drops the Unassigned row).
- Idempotency keys on E-WORK-ASSIGN, optimistic rows from a 200 body, and automatic retries.
- Backend, OpenAPI or `schema.d.ts` regeneration, `architecture/**`, `design/**`, `src/shell/**`, and new npm dependencies.

## Assumptions
- Work ids W-3301 to W-3306 and the no-fixture id W-3399, with cases C-3301 to C-3306. Reason: F-36's block is W-33xx (`NIGHT-LOG-2026-11-18.md:32`). No tasks, so no T- ids.
- The board fixture keeps the board's "Tamarind Loans · TL-RFP-2026-014", which W-2112 shows later in its life. Reason: fidelity, and the sample story agrees (Tunde later runs it).
- Each fixture has its own case, although D-RFP-INTAKE places RFPs on one fixed intake case. Reason: keeps tests independent; the contention is G-23-5, the backend's to settle.
- An Unassigned row opens the panel URL, and an item without `assign` goes on to `/work/<id>`. Reason: the list item has no field saying whether it can be assigned; this keeps other Unassigned work landing where it does today.
- `assign.role` is read as the assigner's acting role. Reason: readiness and G-24-1; F-31 reads it differently, and the backend is asked to define it.
- One proof file per assignment. Reason: the proposed request takes one `evidence_id`.
- With several roles, the backend's default `assign.role` is chosen. Reason: G-24-1 says "keep `role` as the default", and it is the backend's statement, not the browser's (as D-113 allowed for F-31).
- The wording "Assign accountable PM", "Choose a PM", "n people can prepare RFPs here", "No one can prepare RFPs here yet.", "<reference> is now with <name>.", "Not confirmed …" and the fixed "What happens next" sentence is frontend copy, not business rules. Reason: sources are silent; the approver may escalate.
- The board's intro sentence ("Who may assign is set by PSL in Setup.") is shown as drawn. Reason: it describes the backend's rule without the page applying it; it is checked at product acceptance.
- Persona `pmo_lead` is mock-only and decides only which sample list the mock serves. Reason: no real approvers are named; Head of PMO = PMO Lead (13 Nov decision).
- Ports 4960/4961. Reason: no other spec uses 496x.
