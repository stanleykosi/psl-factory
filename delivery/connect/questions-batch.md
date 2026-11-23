# Questions for the design engineer (batched, D-180)

Lanes append here; the coordinator brings them about twice a day and writes the answers back.

## Lane A

### F-60 · Account set-up from an invitation (SCR-17 set-up boards, `/staff/join/`)
Context: live accept needs a confirm field, does not sign the person in, and answers every unusable invitation the same way (spec `delivery/features/F-60/spec.md`). F-60 builds on F-58 and is parked until these are answered.
1. Confirm password: the API needs it; the boards draw one field. (a) Recommended: add "Confirm new password" under "New password". (b) One field with a show-password toggle, sending the same value as confirm (a typo is not caught).
2. WhatsApp number block (no operation, G-SCR17-5). (a) Recommended: leave it out, as D-177 did for removed content. (b) A disabled field, "Not available yet".
3. Password hint "At least 12 characters" (no rule in the API, A-47). (a) Recommended: no hint; after a refusal the server's message shows. (b) A hint with no number: "Choose a password that's hard to guess."
4. After "Finish setup" (not drawn; the backend does not sign them in). (a) Recommended: "Your account is ready. Sign in with <email>." with a Sign in button to `/sign-in`. (b) Ask the backend to sign them in on accept (backend change, and the admission call A-48). (c) Go to `/sign-in` with a small "Your account is ready" note (changes F-58's page).
5. The invitation's end date (live gives `expires_at`). (a) Recommended: one secondary line, "This invitation works until 26 Nov 2026, 15:00." (b) Leave it off, as the board.
6. Welcome line when the invitation gives several workspaces with different access. (a) Recommended: one sentence per access group. (b) A short list under "You've been given:".
7. Wording for a link that cannot be used (no board). (a) Recommended: "This invitation can't be used. It may have expired or already been used. Ask the person who invited you to send a new one." plus "Already set up? Sign in". (b) The same without the sign-in link.
8. Name in the welcome line (boards say "Sola"; live gives the full name). (a) Recommended: the name as returned. (b) The first word only.

### F-61 · Alerts list, drawer and alert settings on the live API (SCR-15 default and settings)
Context: live `GET /notifications` and `/me/alert-preferences` are much smaller than the boards (spec `delivery/features/F-61/spec.md`, "Conflicts with the boards"). F-61 is parked until these are answered.
1. Alert rows have no agent avatar, name or time in live (A-42). (a) Recommended: show title over subject and detail, no avatar, no time. (b) Keep a neutral PSL mark in the avatar slot so the board's row alignment holds. (c) Wait for the backend to add `at` and `agent`.
2. Settings without per-event switches, digest and quiet hours (A-44). (a) Recommended: only the Email and WhatsApp switches, with Ready state and receipts. (b) Also show the old rows greyed out, "Not available yet". (c) Hold the settings page until the backend decides.
3. Search, agent filter, unread filter and totals (A-43). (a) Recommended: remove them for this release; show "N alerts loaded" with the as-of time. (b) Keep an unread-only toggle and text search over the loaded list, worded "filtered from the loaded alerts". (c) Keep the full toolbar and wait for paging.
4. The recent-deliveries list is new on the settings board. (a) Recommended: a plain list under the switches. (b) A one-line summary of the last delivery per channel. (c) Leave receipts out until the board is redrawn.
5. An alert with no usable link (no work id in its link). (a) Recommended: the row is not clickable and has a Mark as read button. (b) The row stays clickable and only marks it read. (c) Hide such alerts.
6. Wording of the receipt states. (a) Recommended: Queued, Not confirmed, Delivered, Held. (b) Waiting to send, Could not confirm, Delivered, On hold. (c) Your own wording.
7. D-ALERTS-ENTRY, the part still open: the account menu's "My roles" and "Delegate while away" links lead nowhere, and no phone board shows how the account page (password change, SCR-15 account boards) opens. (a) Recommended: for now the account menu shows only the person's name and Sign out (as F-58 built it), and the phone menu gets an "Account" row opening `/settings/account`; draw "My roles" and "Delegate while away" later. (b) Draw both links now, pointing at the setup screens. (c) Leave the account tab unbuilt this release.

### F-62 · Verified outputs and All exceptions on live GET /work (SCR-14, SCR-10)
Context: live `GET /work` rows carry no proof, reference, kind or totals (spec `delivery/features/F-62/spec.md`, "Conflicts with the boards"). F-62 is parked until these are answered; F-63 (My work) reuses its list adapter.
1. How do people reach Verified outputs? (a) Recommended: a "Verified" link under the My work heading area for now (a tab-style link to `/verified`; F-63 decides the final place), no top-bar change. (b) Add "Verified" to the top bar for everyone (shell change, the boards' top bar has no such item). (c) Leave `/verified` URL-only until F-63.
2. SCR-14 Facts earned and Proof columns, no data in the list. (a) Recommended: hide both and rely on Open output. (b) Show the column headers with "Open the item to see" text (adds clutter). (c) Read each row's work item to fill them (up to 8 extra reads per page, slow, partial).
3. Heading counts "6 of 28" (SCR-14) and the open-exceptions count (SCR-10). (a) Recommended: show "{n} shown" only, plus "so far" while more pages exist. (b) Hide any count. (c) Count only the loaded rows and call it the total (wrong when more exist).
4. "Since 11:02" on exceptions becomes "Last updated". (a) Recommended: keep the board's position under the tag, wording "Last updated 11:02". (b) Drop the time from the tag cell and keep one "Last updated" column. (c) Keep the word "since" (misleading).
5. Exception kind filter chip. (a) Recommended: remove; line filter only. (b) Keep a state filter applied to loaded rows only (hides rows that exist on later pages). (c) Wait for A-38 before building the filter at all.
6. Coverage line ("may be incomplete", "n more items are still being checked") appears on both pages, not drawn. (a) Recommended: a quiet secondary line under the list. (b) A callout above the list. (c) Hide it (the list then looks complete when it is not).
7. Exception rows that are not exceptions (ready, waiting, verified) can come back on this queue. (a) Recommended: show them with their own tag. (b) Hide them on the client (the list then differs from what the server reports and the "shown" count undercounts). (c) Show a "Not an exception" tag.
8. `action_needed` tag word. (a) Recommended: "Action needed", the existing state-tag word and the board's. (b) "Blocked", the old v7 wording (no board draws it).

### F-64 · Decision desk on the live API (SCR-03 default, done, not-yours, stale, own)
Context: the live decision needs one evidence item the boards never draw, and live has no chain, basis, preparer, reason or next-step text (spec `delivery/features/F-64/spec.md`, checked against the desktop boards). F-64 is parked until these are answered.
1. Evidence picker (not on any board). The live decision needs one evidence item. Options: (a) a short radio list under the verdict buttons, labelled by source and version, nothing pre-selected, buttons off until one is picked (recommended: smallest, honest); (b) a drop-down in the note area; (c) pre-select the newest item (rejected: A-18 unanswered, would cite evidence the person did not choose).
2. Own board (prepared by you) and the "why you cannot decide" sentence. The live read has no reason and no preparer. Options: (a) show the not-yours board with the generic sentence for every case and leave the own board unreachable until the backend answers A-19 (recommended); (b) show a softer "You can't decide this one" without any reason; (c) hold the read-only boards and show only the facts.
3. Approval chain strip ("your step 2 of 3"), basis line, "what changed since last version" list, prepared-by name. No live source (A-19, A-21). Options: (a) hide each part and show nothing in its place (recommended); (b) show the row with "Not available yet" in the value; (c) keep the part but fill it only from what exists (on the stale board, version, amount and recipient comparison only).
4. Comment box on the not-yours board. The live comment write exists but `can_comment` is not exposed, so we cannot tell who may comment. Options: (a) show the box only on the read-only board and let the server's 403 turn it off (recommended); (b) hide the box until the backend says who may comment; (c) show comments as read-only text only.
5. Recipient change warning. Live data has `recipient_change{earlier,current}`, no board draws it. Options: (a) a single line in the amount/recipient rows when it changed (recommended); (b) a warning callout above the rows; (c) leave it out.
6. Decided-by on the done board. The reply has no decider or time. Options: (a) take actor and time from the decision history and hide the line if missing (recommended); (b) drop "decided by" always and keep only verdict and note; (c) show the signed-in person's name and the page's own clock time (rejected: not a record).
7. Pager "decision 2 of 5" and the phone bar's queue note. Options: (a) drop it unless the live decision list loads and contains this task, then fill from that list (recommended); (b) drop it always; (c) show the list count only ("5 waiting").
8. Parts of the done board with no live source: "Next step. Chidi will issue it and email it to…", "Paid is tracked separately…" sentence, the SENT/RECEIPT strip detail, and the "Still waiting on you" list. Options: (a) keep the "Paid is tracked separately" sentence (fixed policy copy), hide the Chidi next-step sentence and fill the "Still waiting on you" list and "Next decision" link from `GET /work?queue=decisions` only, hiding them if the list fails (recommended); (b) hide the whole "what happens next" block; (c) replace the next step with the work state label from `work_state`.
9. Stale board sentence "Version 3 was drafted at 10:46 after the billing contact changed" and the agent note "Chidi redrafted it…". The live read has no draft time, cause or agent note. Options: (a) say "A newer version arrived while you were reading. Version 2 can no longer be approved." and drop the time, cause and agent note; the comparison table (amount, recipient) stays (recommended); (b) add the time of the reload as "seen at hh:mm"; (c) keep the agent block empty.
10. Not-yours board: the "Ada Okafor was alerted at 10:42 by WhatsApp and email" line, the "You hold Finance on this project…" reason, and the BASIS value. No live source. Options: (a) keep the heading "Not your decision", the amount, "Waiting for {task.role}" and the comment box; hide the alert line, reason and basis (recommended); (b) show the line "Not available yet" in each; (c) hide the comment box as well (Question 4).
11. Default board sentence "Only a Finance Lead can decide. You are Finance Lead." Options: (a) draw "Only a {task.role} can decide." from the task and drop "You are …" because the page may not infer the person's role from /me (recommended); (b) drop the sentence; (c) fill "You are …" from /me (rejected: INV-ACCESS says /me does not decide what is offered).
12. Own board (Finance canvas) shows "Prepared by Bisi Ade (you) · with Chidi", "Asked: Ada Okafor · Finance Lead 12 Nov 10:20" and "Waiting · Finance reviewer". Preparer, asked person and time have no live source (A-19, A-21). Options: (a) leave the board built but unreachable, as in Question 2 (recommended); (b) reach it only when a later backend answer provides a `prepared_by_you` flag; (c) show it with the three lines hidden.

### F-65 · Overview, the factory floor, on live GET /overview (SCR-06)
Context: live gives one recorded-work total per line, no in-progress/needs-a-person/stopped totals, no station counts and no floor grouping (spec `delivery/features/F-65/spec.md`). F-65 is parked until these are answered.
1. The four headline totals (IN PROGRESS, NEED A PERSON, STOPPED, VERIFIED THIS MONTH) and the phone's two-figure summary; the live API returns none (A-34). (a) Recommended: keep the board's place but show one line "Totals are not available yet." (b) Hide the whole block until the backend adds them. (c) Show the four labels with "Not available yet" under each.
2. Station squares and "needs a person" marks on each row; the live API has no stations. (a) Recommended: remove the squares and show each line as a title, a number and an "Open work" link. (b) Draw one square per line with its `total`, in the neutral colour only. (c) Hide the station track and keep only the floor's sum.
3. The tag on each row (Stopped, Waiting, Verified and so on). (a) Recommended: a neutral "Not available yet" tag. (b) Hide the tag column. (c) Replace it with the recorded-work count as a tag.
4. The eight floors are rebuilt from our own key-to-floor map, and PMO lines have no floor. (a) Recommended: a ninth "Other lines" floor, shown last, with no avatar. (b) Add a "PMO" floor with a new subtitle and an existing avatar. (c) Show one flat list of lines with no floors.
5. The 3D floor has no stations to show. (a) Recommended: one machine per line with its total, neutral colour, strip with an "Open work" link. (b) Keep the 3D switch but show one block per floor with the floor's sum. (c) Hide the 3D view for this release and show flat only.
6. Strip opened from a square in the flat view lists the station's work (design D-165). (a) Recommended: remove it; "Open work" goes to the queue for that line. (b) Keep a small inline strip showing the line's count and the same link.

### F-66 · Assistant on the live conversation API (SCR-05)
Context: live has no image upload, thread titles, status badges, step lines or paging (spec `delivery/features/F-66/spec.md`). F-66 is parked until these are answered.
1. Image attach (board shows it on the composer). The live API has no upload. Options: (a) remove the control entirely and record a deviation (recommended); (b) keep it disabled with "Not available yet"; (c) keep it and send nothing (the image would be dropped silently; not advised).
2. Thread titles and status badges in the list (boards show a title and a Working / Answered / Can't / Drafted tag). Live rows have neither. Options: (a) show "<Agent> · Project|Department · Updated <time>" and no badge (recommended); (b) keep a badge slot that fills only after opening the thread; (c) fetch every thread to derive a badge, which is up to 25 extra reads per list view.
3. "What I did" step lines under an answer (boards draw them). No live field. Options: (a) hide them (recommended); (b) show the sources as the only evidence line; (c) wait for the backend.
4. Polling and the working card (board "working" shows run start and progress). Options: (a) working card with "Asked at <time>" and polling at 3 s then 10 s (recommended); (b) manual "Check again" button only; (c) polling with no card text beyond a spinner.
5. @mention picker (project, work, document, person). Replaced by the source picker (labels only). Options: (a) replace as built (recommended); (b) keep a text-only "#" shortcut that opens the same source list; (c) hide the control until sources are richer.
6. Cannot-answer card (board shows a reason and buttons). Live gives status text only. Options: (a) show the text as the reason, with a "Ask a different question" focus button only (recommended); (b) drop the reason line; (c) keep the board's suggestion buttons using `question_options`.
7. Separate person and agent bubbles with edit (board). Live has one object per question. Options: (a) two bubbles per message, no edit (recommended); (b) one card with question above answer; (c) keep edit disabled with a tooltip.
8. Conversation list paging (board shows page size). Live has none, max 25. Options: (a) remove the size control and show "<n> loaded" (recommended); (b) keep a size control that cuts the client list; (c) show "Latest 25" as a fixed label.

## Lane B

- **F-74 · B1. Setup without a workspace (backend B-21, short-list 4).** Every live Setup read and save needs a workspace; our Setup pages are organisation-wide. How should Setup open?
  1. (Recommended) Setup opens with a workspace picker; rules, delegation and templates show for the chosen workspace. We ask the backend which workspace holds organisation-wide values and switch when they answer.
  2. Wait for the backend to add an organisation-level Setup read before connecting Setup.
  3. Pin Setup to one named workspace that PSL chooses.
  Context: we are building the picker now (option 1) so Setup is not held up; options 2 and 3 only change which workspace it opens on.

- **F-74 · B2. Workspace picker on the Setup frame (not on the boards yet).** A picker at the top of Setup, filled from your active projects, choosing which workspace's rules, delegation and templates you see.
  1. (Recommended) Approve a simple picker in the Setup header, with the chosen workspace kept in the address so reload and links work.
  2. Draw it on the canvas first, then build.
  Context: needed whichever way B1 goes, unless one fixed workspace is chosen.
- **F-74 · B3. Setup saves become "draft, then review".** Live never puts a rule or delegation change straight into force; it is saved as a draft that someone reviews and activates. Every save also needs a proof file, and the backend has not said how the screen creates one (B-25).
  1. (Recommended) This release connects Setup reads only; the Save, Edit and Replace controls stay visible but disabled with the line "Changes open once proof upload is connected", and we build the draft-and-review step when the backend answers.
  2. Build "Saved as draft, waiting for review" now and hold only the final send.
  3. Hide the edit controls entirely until then.
- **F-73 · B4. Clients without an amount owed.** In live a client is a group of workspaces with no owed amount, money panel or "blocked" lines.
  1. (Recommended) Hide the owed column, money panel and blocked lines for now.
  2. Keep them and show "Not available in the live data yet".
- **F-73 · B5. Client id in the address.** Live has no client id. The page address would use the group key (or the workspace id when a project has no group); the key can change if grouping changes.
  1. (Recommended) Accept the group key in the address.
  2. Use a name in the address and look it up.
- **F-73 · B6. Adding a billing contact waits.** Adding a billing contact needs a proof file and the shared "attach proof" picker does not exist yet (backend question 1).
  1. (Recommended) Connect the client reads now and keep "Add billing contact" disabled with the reason, in a later feature.
  2. Hold the whole Clients connection until the picker exists.
- **F-72 · B7. Document review parts with no live source.** Live has no agent notes per section, "changed since" marks, Compare, per-check Done/Held/Blocked list, project reference or TEST TEMPLATE tag; the returned banner is a status word only.
  1. (Recommended) Drop those parts for this release; show the returned state as its status text, and the crumb from the project title alone.
  2. Keep them as "Not available yet" placeholders.
- **F-72 · B8. Reject and the approve note.** Live offers approve, return and reject, and requires a note on approve.
  1. (Recommended) Offer approve and return as drawn, require the note on approve as live does, and leave reject out until you draw it.
  2. Add a Reject button now with the same note box.

- **F-70 · B9. Project list and journey: nine board changes from live data.** Full options in `delivery/features/F-70/spec.md` ("Conflicts with the boards"). We build option 1 of each; say "accept all" or name the ones to change.
  1. (Recommended) Accept all: project list loses the next-milestone column, reference, count badges and rows-per-page (shows "N shown, more available"); the journey loses "What is next", Tola's summary and "Station n of m"; the facts strip has four cells (invoices verified and paid have no live source) with "Figures may be partial." when finance is partial; the Delivery tab is hidden and its address says "not available yet"; work tags are one neutral colour with the live words; no tab counts; started and updated times are shown on each work row.
  2. Keep the missing parts as "Not available" placeholders instead of removing them.
  Context: each gap has a backend question (B-2 to B-6, B-33, B-34); we switch them on when answered.

- **F-74 · B10. Setup board changes from live data.** Full list in `delivery/features/F-74/spec.md` ("Conflicts with the boards"). We build option 1.
  1. (Recommended) Accept all: workspace picker in the header (B2); edit controls visible but disabled (B3); templates lose line, TEST TEMPLATE tag, updated by, version count and kind; delegation is a read-only list of role, names and dates (no reason or status); rules lose per-row Edit, "holds N pieces of work", effective from, used by and the roles count ("not set" stays); a new "You can't open this workspace's Setup" state on each tab.
  2. Keep the missing parts as "Not available" placeholders.
- **F-73 · B11. Clients board changes from live data.** Full list in `delivery/features/F-73/spec.md`. We build option 1.
  1. (Recommended) Accept all: owed column, money panel and blocked lines removed (B4); the list mixes client groups and projects with no group, same row design; a client group has no single billing contact until the backend answers (each project links to its own contacts); small read-only "Project contacts" and "Show history" blocks; the billing contact form is disabled with its reason (B6); an "Unknown" state tag in the neutral style.
  2. Leave out the added "Project contacts" and "Show history" blocks.

- **F-72 · B12. Document review small board changes.** Details in `delivery/features/F-72/spec.md`. We build option 1.
  1. (Recommended) Accept all: on phone, Approve opens the same note sheet as Return (live needs a note on approve); the desktop note label becomes "Note for the PM"; a blockers list shows only when live reports blockers (explains why approve is refused); a "Not the current version" tag shows only on an older version.
  2. One-tap Approve on phone with a fixed note (not recommended: the note would not be the person's words).

- **F-76 · B13. Staff accounts: a read-only list now?** Who holds Admin (D-ADMIN-AUTHORITY) is still waiting for PSL, so invite, deactivate, restore and role changes cannot be built. Live can list staff and open one person.
  1. (Recommended) Build a read-only staff list and person page now, with no write controls. The board's people count, "Last signed in", invite and deactivation dates and "role per workspace" wording have no live source and are left out. Who may open it follows the server's answer (backend A-53).
  2. Wait for PSL's Admin decision and build the whole screen at once.
- **F-77 and F-78 (for PSL, no action from you):** the costing rule page waits on D-COSTING-RULE, and "Mark a milestone complete" waits on who may press it and whether it starts the invoice draft (the live command now exists). Both are parked as BLOCKED.

- **F-79 · B14 to B17. Month-end and payments list board changes.** Details in `delivery/features/F-79/spec.md`. We build option 1 of each.
  1. (Recommended) Accept all: B14 the agent notes, next-action button, "received this month", bank-data date, coverage sentence, row and filter counts, milestone label, per-row colour and month-end "N of M" are hidden (no live source), the strip gains a "data as of" cell and the State filter keeps the five live states; B15 "overdue by" becomes AGE ("N days") until the backend says what overdue means; B16 a "Partial result" notice when the data is partial, the basis beside each figure, one total per currency and basis, and month-end cash reads "By project" when it is not one figure; B17 the reminder, record-payment and review-payment actions show disabled with a reason when the server gives no link.
  2. Keep the missing parts as "Not available" placeholders.

## Lane C

### LC-Q1 · F-85, F-87 · Work item parts the live API does not give
The approved work item shows a station track (who holds each step), the six facts strip (drafted, reviewed, approved, sent, receipt, verified) and the agent's numbered steps. Live `GET /work/{id}` has none of these (backend question 2). What should the page show until the backend answers?
1. **(Recommended)** Hide the three parts. Show what live gives instead: the state tag, next step, why it is stuck (`blocker`), the current activity line, and the link to the finished output.
2. Keep the three parts on the page with a plain "not available yet" note.
3. Build our own station track from the history list. This is an engineering guess, not a backend fact, and it may show the wrong holder.

### LC-Q2 · F-87 · "Confirm what happened" after an uncertain send
In the design, a person with recovery authority chooses delivered, not delivered or unknown and attaches proof. In live, reconcile is only a backend lookup: the person presses it and the backend decides (backend question 10).
1. **(Recommended)** Show one "Check what happened" button that runs the lookup, then show the state it comes back with. Keep the choice-and-proof panel out until the backend answers.
2. Keep the panel visible but disabled, with a note that it is waiting on the backend.

### LC-Q3 · F-86 · Lines Start work cannot submit yet
Some lines say `can_submit_via_api: false`, and the invoice start is not among the live lines (backend question 8).
1. **(Recommended)** List those lines as unavailable with a one-line reason, and leave out the invoice start until the backend answers.
2. Hide them from the chooser completely.

### LC-Q4 · F-85 · History list: filters, counts and sentences
The approved History view has per-filter counts, rows written as sentences with an actor kind, and "show more". Live `GET /work/{id}/history` returns at most 30 rows of `{at, station, status, actor?, reason?, evidence_id?}`, filtered only by worker, decision or evidence, with no counts and no paging (backend question 5).
1. **(Recommended)** Keep the filter tabs but drop the counts and "show more"; write each row from `station` and `status` words plus the actor and reason when present; say "Showing the latest 30" with the as-of time.
2. Hide the filters too and show one list.
3. Hold History until the backend adds counts and paging.

### LC-Q5 · F-85, F-87 · Buttons the boards draw that this feature leaves out
The work item boards draw Resume, Cancel and "Confirm what happened" buttons and the decision card. Their writes are in F-87 and the decision screen is a separate feature. Until F-87 merges the page shows no write buttons (decisions waiting link to their own page).
1. **(Recommended)** Leave the buttons out until F-87 merges; the page shows state, next step and blocker only.
2. Show them disabled with "Not available yet".

### LC-Q6 · F-85 · Fields the boards show that live does not give
Reference (for example "INV-0412"), started by, started at and amount have no live source on `GET /work/{id}` (backend question 7, A-14). Live gives the work id, `owner` and `updated_at`.
1. **(Recommended)** Drop reference, started by and amount; show "Updated" from `updated_at` and "With" from `owner` when there is one.
2. Show the numeric work id as the reference.

### LC-Q7 · F-88 · Assigning the PM now needs proof and a reason
The approved Assign PM drawer draws proof as optional and a short optional Note. Live requires both a proof (chosen from the list the backend offers for that RFP) and a written reason (up to 4000 characters), and has no Note field (backend question C-12).
1. **(Recommended)** Make "Proof" a required choice from the offered list and replace Note with a required "Reason for choosing this PM"; drop "(optional)".
2. Keep the drawer as drawn and hold Assign PM until the backend makes both optional.

### LC-Q8 · F-88 · Log RFP: the Note and the client name
The approved Log RFP form has a free Note and a client picked by name. Live stores no note on a received RFP, and the client picker lists only the organisations where you may record a received bid; a new client is typed as a name (backend questions C-9, C-10).
1. **(Recommended)** Remove the Note. Keep the organisation picker (required) and add a plain text "Client name as written in the RFP", optional.
2. Remove the Note and show only the organisation picker.
3. Keep the Note on screen and hold it until the backend stores it.

### LC-Q9 · F-88 · After logging or assigning: what the success words can say
Live returns no work item id after logging and no PM name or "what happens next" after assigning (backend questions C-7, C-13). The drawn success lines name the PM and say the PM is alerted.
1. **(Recommended)** After logging, say "RFP logged" with the reference and received time read back from the receipt and a link to the Unassigned list. After assigning, say "PM assigned" with the person's name from the chosen list entry, only after the list is re-read; leave out the "alerted" and next-steps lines.
2. Keep the drawn sentences and accept that they may not be true.

### LC-Q10 · F-86 · Weekly report start form: what the live body changes from the board
The SCR-04 weekly board draws Project, Week ("Must have ended; up to 8 days") and a Template line reading "Client weekly report · test template v1". The live `POST /work` weekly body also requires a `reference` (1 to 160 characters), carries the template only as an id with no name, and has no "up to 8 days" rule in the contract.
1. **(Recommended)** Add one text field "Reference" under Week, leave the template line out (send `template_id` and `content_id` as null), and drop the "up to 8 days" help line; the server's own message shows if the week is refused.
2. Keep the Template line as drawn and fill the words from a source the live API does not serve yet (needs a backend change).

### LC-Q11 · F-86 · Upload on the weekly form
The weekly board draws no file field and the live weekly body has no field for an uploaded file (`upload_id` has nowhere to go). The first slice still builds the upload for the lines that need it.
1. **(Recommended)** Build the upload box (the F-85 evidence picker) in Start work but show it only on lines whose body takes a file; the weekly form shows none.
2. Show an optional "Add files to this project" box on the weekly form that uploads to the case but is not sent with the start.

## Answers, batch 1 (23 Nov 2026, D-182)

Every recommended option above is accepted ("Hide, accept all recs"), including LC-Q1 (hide until backend), F-65 (as recommended) and F-76 (read-only list now). Lanes: unpark these features and build them as their specs recommend.
