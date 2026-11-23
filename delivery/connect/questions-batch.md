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

### F-59 · Forgotten password: ask for a link, set a new password (SCR-17 reset boards)
Context: the reset boards draw only "ask" and "Check your email."; live gives no link validity and one answer for every unusable link (spec `delivery/features/F-59/spec.md`). Q4, Q5 and the confirm field in Q2 follow D-182's answers to F-60 Q4, Q3 and Q1, so they are settled; Q1, Q2 (building the undrawn state), Q3, Q6 and Q7 are new. F-59 builds on F-58; until these are answered it is parked.
1. Link validity in the ask sentence. The board says the link "works for 30 minutes"; the API returns no validity (A-47).
   - (a) Recommended: "Enter your work email. If it has an account, we'll send a reset link." (no duration, same call as D-177 for removed numbers).
   - (b) "...we'll send a reset link that works for a short time." (hints at expiry without a number).
2. The new-password state has no board (the reset boards draw only "ask" and "Check your email.").
   - (a) Recommended: build it from the sign-in form column and the set-up pattern ("Choose a new password", two fields, "Change password"), then review it at the fidelity run.
   - (b) Hold the page until a board is drawn (the whole flow stays unusable meanwhile).
   - Same as F-60 Q1 for the second "Confirm new password" field (the API needs `new_password2`): recommendation there is to add it; here it is built as in F-60 Q1(a), to be changed with it.
3. The unusable-link state has no board.
   - (a) Recommended: heading "This link can't be used", text "It may have expired or already been used. You can ask for a new one.", primary link "Send me a new link", text link "Back to sign in".
   - (b) The same without the "Send me a new link" button (only "Back to sign in").
   - (c) Name the exact reason (not possible: the API answers the same for every reason). Same pattern as F-60 Q7; the wording here differs because the next step is asking again, not asking an administrator.
4. After the change (no board; the backend does not sign the person in).
   - Same as F-60 Q4, with the recommendation (a): a plain "Your password is changed." state with a "Sign in" button to the F-58 page. It is drawn as heading and text rather than a success callout (D-151).
5. Password hint line under "New password" (A-47).
   - Same as F-60 Q3: recommended (a) no hint; after a refusal the server's message shows.
6. "Use a different email" on "Check your email." (not drawn).
   - (a) Recommended: keep the small text button so a mistyped address can be fixed without reloading.
   - (b) Remove it; the person uses the browser back button or reloads (matches the board exactly).
7. F-58's plain "Forgot your password?" exception. The sentence returns to the drawn link in this feature.
   - (a) Recommended: link only, no helper words, centred as D-178 placed the sentence.
   - (b) Keep a helper line such as "We'll email you a link." under it (adds copy the boards do not draw).

### F-58 · Product acceptance of sign-in (PR https://github.com/stanleykosi/psl-factory/pull/100)
Context: every review passed on head `57ae81e8` (see merge-batch.md). Product acceptance is yours to give.
1. Accept F-58 sign-in and sign-out as built on `57ae81e8`? (a) Recommended: accept, and approve the merge. (b) Accept, but first make sign-out load `/sign-in` fresh (SEC-1-1, a small fix round). (c) Request changes (say which).

### Lane A · API 1.24.0 presentation questions (D-185)
Context: the re-specs on 1.24.0 switch the hidden parts back on; only these presentation choices are new. Each has a recommendation first. F-60 has no new question (its ready state is D-182 F-60 Q4).

**F-59 (forgotten password)**
8. Where the 30-minute and 12-character figures come from (new with 1.24.0; presentation only).
   - (a) Recommended: show them as the board draws, kept in one constants file that names backend answer A-47, because the API returns no value for either. The page never enforces them.
   - (b) Show them only once the backend returns them in a response (the figures stay hidden; the board's lines are missing until then; not recommended since PSL has stated the policy).

**F-61 (alerts)**
7. Wording of the daily summary line (new, A-44; presentation only). Options: (a) recommended: "Today, 23 Nov: 3 need you, 2 new updates, 1 older unread" as one quiet line above the groups, plain text, no card; (b) a small three-figure strip (Need you / New today / Older unread); (c) show only the "need you" figure.
8. Paging control on `/notifications`. Options: (a) recommended: a "Load more" button under the list with "Showing N loaded, M unread"; (b) numbered pages using `page`; (c) infinite scroll.
9. Rows with no agent or time (reminders and older alerts). Options: (a) recommended: neutral avatar slot and no time, so the row alignment holds; (b) no avatar and no time (compact rows); (c) show "Earlier" instead of a time.

**F-65 (Overview)**
7. Totals and squares are sampled from the 50 most recent items. (a) Recommended: show "at least N" and a coverage line "Counted from the 50 most recent items you can see" when limited. (b) Show the number plain with a small "(sample)" mark. (c) Hide the four totals when limited.
8. The row tag is still not supplied, but `stopped` and `needs_person` are now known per line. (a) Recommended: keep the neutral "Not available yet" tag until the backend gives a status. (b) Derive the tag in the page: "Stopped" if `stopped` > 0, "Waiting" if `needs_person` > 0, else none. (c) Hide the tag column.
9. The floor number (exact, open work) and the station squares (sampled) can disagree. (a) Recommended: show both with the footnote saying station figures come from recent items. (b) Show the floor number only when station figures are not limited. (c) Show the sum of station counts as the floor number, with the same "at least" rule.


**F-66 (Assistant)**
1. Sent images in the thread. The API returns only image ids on a message. Options: (a) "<n> images attached" text (recommended); (b) fetch the case file list and show thumbnails from `download_url`, one extra read per thread; (c) show nothing after send.
2. "Drafted" in the list. The list status cannot say drafted. Options: (a) no Drafted badge in the list, only in the thread (recommended); (b) show "Answered" with a small draft mark after opening; (c) read each thread (up to 25 extra reads).
3. Department thread entry. Options: (a) a "Whole department" switch on the new-conversation sheet, default off, with the chosen project as the anchor (recommended); (b) a separate "Department chat" button; (c) hide department scope.
4. `held` wording. The backend gives no reason. Options: (a) one fixed sentence "I couldn't complete this. Try again, or check that you still have access to this project." (recommended); (b) shorter "I couldn't answer this."; (c) show the raw status.
5. "Answered <time>" from `finished_at` on settled cards, not in the boards. Options: (a) show it small under the answer (recommended); (b) leave it out.
6. Image chips use local thumbnails before send and a remove button. Options: (a) as written (recommended); (b) filename-only chips.

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

### Batch 2 (lane B)

- **F-76 · B18. A person page that no board draws.** Live gives each person's access workspace by workspace (`GET /staff/{id}`), but SCR-21 draws only the list.
  1. (Recommended) Add a plain read-only person page at `/setup/staff/<person>` in the existing Setup style: name, status and access per workspace. We build this now.
  2. No person page; the list only, and the per-workspace access is not shown.
  Context: no write controls either way; invite, deactivate and roles wait for PSL (D-ADMIN-AUTHORITY).

### Batch 3 (lane B)

Plain hides in these two specs are covered by D-182 and are not asked again. We build option 1 of each item below.

- **F-71 · B19. Money and Milestones tabs: live data the boards do not draw.**
  1. (Recommended) Show the "figures may be partial" warning, a "Due <date>" line, several invoices per stage as a stacked list, and invoice rows that are not contract stages.
  2. Show none of them (the table matches the boards, but partial figures carry no warning).
  3. Show only the partial-figures warning.
- **F-71 · B20. Milestones tab for someone who may not see Finance figures.**
  1. (Recommended) Show the recorded completions plus one line: "Contract amounts, invoices and payments aren't available to your role."
  2. One empty state and no completions.
  3. Hide the Milestones tab for them.
- **F-71 · B21. "Recorded completions" list.** Completions and contract stages can't be joined in live (backend B-47).
  1. (Recommended) A separate list under the table.
  2. Leave it out (people without Finance figures then see nothing).
- **F-71 · B22. Paid column wording.** Live gives amounts only, no paid word.
  1. (Recommended) "Paid <amount> · Owed <amount>", with Unknown for each missing amount.
  2. A dash when both are missing (hides the unknown; not recommended).
- **F-75 · B23. Severity "Critical" in Registers.** The boards draw Low/Medium/High; live also sends Critical.
  1. (Recommended) Its own neutral tag with the live word.
  2. Show it as High.
  3. Hide Critical rows.
- **F-75 · B24. Escalations register.** Live returns an Escalations section that no board draws.
  1. (Recommended) Leave it out of the register switch for now.
  2. Add a fifth register (needs a board).
  3. Fold it into Issues.
- **F-75 · B25. Changes, Emergencies and RFPs columns.**
  1. (Recommended) Use the Issues columns, with "—" where live has no value.
  2. Give each register its own columns (needs a board).

### Batch 4 (lane B, API 1.24.0, D-185)

Parts that 1.24.0 now supplies are switched on as the boards draw them (D-185), with no question. Below is only new behaviour. We build option 1 of each.

- **F-73 · B26. Add a billing contact now.** 1.24.0 lets Setup record a billing contact, but only with a proof already recorded on the project; there is no proof upload from the client page. The form also needs customer, client name and role, which the board does not draw.
  1. (Recommended) Build it now: the form picks one of the project's recorded proofs, adds the extra fields, and is disabled with its reason when there is no proof.
  2. Keep it disabled (as in B6) until a proof can be uploaded from the client page.
- **F-74 · B27. Setup saves as "draft, then review".** 1.24.0 has proof upload, delegation drafts, template replacement and review actions. Company settings open without a project (PSL: "Company-wide settings should be accessible from Setup without needing to know a project first").
  1. (Recommended) Build the saves now: every change is saved as a draft that is never shown as in force, review buttons follow what the server allows, a company selector shows only when you manage more than one company, and Templates keeps a project selector (templates belong to a project). Rule rows stay read-only: none of them matches a rule type the backend can draft yet.
  2. Keep Setup read-only this release.
- **F-76 · B28. Staff invite, deactivate, restore and role changes.** 1.24.0 has these commands, but PSL's answer says who may read staff, not who may change them.
  1. (Recommended) Keep F-76 read-only; build the changes as a separate feature once PSL says who may make them (needs PSL).
  2. Build them now for whoever the server allows.
- **F-79 · B29. Month-end and payments wording.**
  1. (Recommended) "Received this month covers N of M projects; K could not be read." only when some could not be read; OWED shows the known part plus "Unknown" with a count of invoices that have no known balance.
  2. Show the total alone with a "partial" tag.
- **F-71 · B30. Money and Milestones: paid word and proof.** Live gives no paid word on the money read (it lives on each invoice's payments) and no proof file route.
  1. (Recommended) No paid word: show the status as given plus Paid and Owed amounts; a "Proof" button shows the recorded name, date and proof version.
  2. Read each invoice's payments to show Paid / Part paid / Not paid.
- **F-78 · B31 (for PSL). Does marking a milestone complete start the invoice draft?** PSL decided the PMO Lead confirms the milestone. The backend only says a Finance handoff is queued. Mark complete stays BLOCKED until PSL answers.
  1. (Recommended) Completion only queues the Finance handoff; Finance starts the invoice.
  2. Completion starts the invoice draft automatically.

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

### LC-Q12 · F-87 · Resume, Cancel and Check what happened: where they sit
No approved board draws a Resume, Cancel or Pause/Continue button on the work item. The awaiting-reconciliation board draws a "Confirm what happened" panel with choices and proof (replaced by one button under LC-Q2). The live work item lists which of these the person may use.
1. **(Recommended)** One small row of buttons under the header, shown only for what the API lists: "Check what happened" (when `reconcile` is listed), "Resume" and "Cancel" (when listed in `available_control`). Cancel asks for a plain yes/no confirmation first. Same row on the phone, stacked. No new colours or panels.
2. Put "Check what happened" inside the next-step callout and the other two in the page menu.
3. Hold the buttons until the design engineer draws them.

### LC-Q13 · F-87 · Pausing and continuing background work
Live lists `background` as an available action but does not say whether the background work is now running or paused (backend question LC-7). Pause and Continue are the two answers to the one call.
1. **(Recommended)** Show two buttons, "Pause background work" and "Continue background work", whenever `background` is listed. The server's answer decides (it refuses the one that does not apply, and we show its message). No guess from the state.
2. Show only "Pause background work" while the item is processing and nothing otherwise.
3. Hold background controls until the backend serves the current setting.

### LC-Q14 · F-89 · Review buttons on the weekly report
The approved review board draws two buttons, "Approve and send" and "Return with a note". Live also allows a third verdict, reject, and lists which verdicts this person may give (`review_verdicts`).
1. **(Recommended)** Draw a button for each verdict the API lists, in the order Approve and send, Return with a note, Refuse. Return and Refuse need a note. No extra confirm: the board's line "Approving sends this exact version to the client" stays above the buttons.
2. Same, plus a yes/no confirm before Approve, because it reaches the client.
3. Draw only the two board buttons and hold Refuse until the design engineer draws it.

### LC-Q15 · F-89 · Editing after a return
The returned board quotes the reviewer's note and has an "Edit your update" button with no edit screen drawn. Live does not serve the note (backend C-16), requires a "reason" with every correction, and carries cites as record ids with no labels (C-15).
1. **(Recommended)** "Returned to you" with no quote. "Edit your update" opens an inline form: four text boxes prefilled from the report, "N records cited" under each (cites kept as they are, not editable), a required "Reason for the change", then "Send for review" and "Cancel".
2. Hold editing until the backend serves the returned note and cite labels.

### LC-Q16 · F-89 · What the reviewer sees before approving
The review board shows the four parts with their records, a byline and a link to the report as the client will see it. Live gives the reviewer a version id and the list of verdicts; the report text is not documented as served to a reviewer, there is no byline, and the client-facing preview is not connected yet (backend B-7, C-17).
1. **(Recommended by the lane C coordinator)** Do not draw Approve and send until the parts are shown on the page: the reviewer must see what goes to the client. Return and Refuse stay.
2. Show the parts the report read serves (nothing more, no link, no byline) and the review buttons whenever the API offers them. If no text is served, the block says so in one line and Approve is still drawn (the spec writer's first pick; it can let a reviewer approve a client message they cannot read).
3. Hold the whole review block until the preview is connected.

_LC-Q10 onwards were added after batch 1 went out; D-182 covers LC-Q1 to LC-Q9 only. They stay open for batch 2, and lane C builds on their recommended options meanwhile._

### LC-Q17 · F-88 · Assign PM: the two confirmation tick-boxes (API 1.24.0)
Live now lets the person upload a file as the proof for choosing a PM, but only with a "checked" confirmation (`checked: true`) sent beside it. Logging an RFP also has a `context_attested` confirmation of the client name and submission instructions typed on the form. The contract gives no words for either.
1. **(Recommended)** Assign PM, when a file is uploaded: a required tick-box "I have checked this file and it supports my choice." Log RFP: an optional tick-box "I confirm the client name and submission details above match the RFP." shown only when a client name or submission detail is filled in.
2. Show no tick-boxes and send the confirmations as true. (Not recommended: it records a confirmation nobody gave.)
3. Hold both until PSL supplies the wording.

### LC-Q18 · F-89 · Comparing a report with its previous version
API 1.24.0 can compare two versions of the same report (changed, added, removed and unchanged sections, with their records). The weekly report read gives only this version's id, not the previous one, and the SCR-25 boards draw no compare. The page shows the report text and the agent's notes without it.
1. **(Recommended)** Leave compare out of this feature. Ask the backend to add the previous version's id to the weekly report read (one field); then add a "What changed since the last version" view in a small follow-up, drawn by the design engineer first.
2. Build a compare view now with no board, using the id the backend supplies later.

### LC-Q17 · F-87 · Wording of "Confirm what happened"
The approved panel says "It didn't arrive. Allow one resend of the same version." and "I can't tell yet. Keep it held and remind me tomorrow." The backend records an observation (delivered, not delivered, unknown) with a reason and proof, and does not resend, remind, verify or approve anything (A-13, answers section 10). The board also has no Reason box and shows proof only for "It arrived", while live needs both for every outcome.
1. **(Recommended)** Keep the three choices with short plain sublines that promise nothing the backend does not do, add a required Reason box, always show the proof picker, and keep only "Your choice is recorded with your name."
2. Keep the board's wording and ask the backend to add resend and reminders (a new behaviour).
3. Hold the panel until the design engineer redraws it.

## Lane D

### LD-Q1 · F-107 · Business-unit totals (SCR-57): build on what the API discloses?
F-44 was held on D-PAYROLL-VISIBILITY: may Finance, the BU reviewer and Chidi see staff count and staff cost per business unit? That decision is still open in `architecture/model.json`. PSL's 23 Nov answers (E-26, E-27, E-30, E-32 in `backend-answers.md`) now have the backend enforce it per person: totals come from the eligible payroll match, a recipient gets the approved BU totals only (no staff counts, no names, no pay rows), a too-small group holds the publication, and approval is an independent review (kind `business_unit`).
1. **(Recommended)** Build SCR-57 on what the API serves to each person and nothing more. A board figure the API does not give that person (for example "Legal (2 people)" for a recipient) is hidden. The merge comes to you in the merge batch, because it shows restricted payroll totals and sends them to the CEO and BU heads.
2. Keep F-107 blocked until PSL records D-PAYROLL-VISIBILITY itself.

## Answers, batch 1 (23 Nov 2026, D-182)

Every recommended option above is accepted ("Hide, accept all recs"), including LC-Q1 (hide until backend), F-65 (as recommended) and F-76 (read-only list now). Lanes: unpark these features and build them as their specs recommend.

## Answers, batch 2 (23 Nov 2026, D-183)

F-58: accepted, merge approved. All recommended options accepted for F-59 Q1 to Q7, B18, LC-Q10 to LC-Q16 (LC-Q16 "Hold Approve", the recommendation), and LC-Q14 "Add Refuse".
