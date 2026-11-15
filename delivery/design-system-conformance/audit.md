# Design-system conformance audit (D-91, step 1)

Audited 15 Nov 2026 on branch `dlv-00-delivery-setup`. Read-only: no code was changed.
Scope: `frontend/src` (app, features, shell, styles) against `design/system/project/` (README.md, tokens.json,
components/*/README.md, components/bundle.css) and `design/components.md` (CMP-01..24).

Method: grep and small scripts over every `.css`, `.ts`, `.tsx` in `frontend/src` (about 29k lines, 199 files),
then reading the code around each hit. Counts are exact where a script produced them and "about" where I counted by eye.
Line numbers are as of this branch. Findings that repeat many times are listed once with all locations.
"Look change?" tells the migration whether to re-check fidelity: **Yes** (visible change expected), **Maybe**
(only in some states or sizes), **No** (markup, behaviour or code only).

## 0. What the baseline looks like (read this first)

- **There is no shared React component layer.** `frontend/src` has `app/`, `features/`, `shell/`, `styles/` and nothing else.
  Every feature writes `psl-*` class markup by hand. Only `shell/` has a few shared pieces (`SampleLabel`, `WarningIcon`, `FrameStates`).
  This is the root cause of most C findings.
- **Colour literals are clean.** The only hex/rgb/hsl match outside the generated files is a comment (`features/alerts/alerts.css:48`).
  Features use `var(--token)` for colour everywhere. Section A therefore concerns sizes, type, motion and breakpoints, not colour.
- **Gaps in the design system itself** (the migration cannot "use a token" where none exists; each needs a design-engineer ruling):
  1. `tokens.css` is generated from `color, spacing, radius, stroke, size, shadow, breakpoint` and font families only
     (`frontend/scripts/gen-styles.mjs:17-21`). There are **no type-scale, line-height, letter-spacing, motion, z-index or opacity tokens**,
     although `tokens.json` defines 20 named text styles (`page-title`, `panel-head`, `tag`, `label` ...) and the README fixes motion at 120ms / 240-320ms.
  2. The spacing tokens are 4/8/12/16/24/28/44. **`components/bundle.css` itself uses 10, 14, 18, 20, 6, 3** (for example `.psl-callout { padding: 10px 12px; gap: 10px }`,
     `.psl-drawer__body { padding: 18px 20px; gap: 14px }`). So feature CSS using 10px and 14px mirrors the bundle, not a mistake of the features.
     Either the scale gains tokens (10, 14, 18, 20) or the bundle is rounded to the scale. Until then, DS-A-2 cannot be fixed mechanically.
  3. CSS custom properties cannot be used in `@media`, so breakpoints can only be matched by literal value (`720px`, `1080px`), never by `var(--bp-phone)`.
  4. `shadow-pop`/`shadow-float`, `scrim` and `focus` tokens exist and are used correctly where applicable (no feature defines its own shadow).
- **Recorded decisions that contradict the README** (flagged, not judged): `shell/sample.ts:1-2` hides the SAMPLE DATA tag unless
  `NEXT_PUBLIC_SHOW_SAMPLE_LABEL=1` ("design decision, 14 Nov 2026"); "Rows per page" selectors come from `D-PAGING r2` (WorkItemHistory.tsx:227). See DS-D-1 and DS-C-ShowMore.

---

## A. Foundations

### DS-A-1 Page titles use eight different sizes
- Where: `styles/shell.css:35` (`.shell-title` 40px, 26px on phone at :45), `features/setup/setup.css:16-17` (34px, area 32px),
  `features/response/response.css:15-16,120` (34, 32, 36px), `features/projects/projects.css:42` (36px), `features/work-item/work-item.css:250` (33px),
  `:398-399` (local `--title-line: 35px`, comment "tokens.css is generated"), `features/my-work/my-work.css:112` (30px empty-state title), `features/decide/decide.css:196` (26px), `features/exceptions/exceptions.css:62` (26px), `features/setup/setup.css:81`.
- Rule: tokens.json `page-title` 34px/37px weight 800, font-stretch 112%, "26px on phones"; `drawer-title` 20/24; `title` 24/28; `display-xl` 40 exists but is not the page title.
- Fix: one `.psl-pagetitle` (or `<PageTitle>`) at 34/37 desktop and 26 phone; drop per-feature overrides. Delete the local `--title-line`.
- Look change: **Yes** (every page header changes size; re-check each title wrap).

### DS-A-2 Off-scale spacing literals (about 330 declarations) and on-scale literals that should be tokens (86)
- Off-scale values (count of declarations): 10px (121), 14px (84), 6px (48), 20px (25), 18px (19), 22px (15), 3px (10), 2px (9), 9px (6), 5px (4), 7px (3), 17/13.5/26/36/40/11px (single). Heaviest files: `work-item.css`, `decide.css`, `response.css`, `my-work.css`, `projects.css`, `setup.css`, `alerts.css`.
- 86 declarations write `4px/8px/12px/16px/24px/28px/44px` as literals instead of `var(--space-n)` / `var(--control-md)` (for example `my-work.css:42-48`, `alerts.css` panel heads).
- Rule: README "Spacing: a 4px base. Panels use space-4, sections space-5, desktop gutters space-6. Every touch target is at least space-7."
- Fix: replace on-scale literals with tokens (safe, no visual change). For off-scale values decide with the design engineer first (see section 0, gap 2): either round to the scale or add tokens. Do not mass-replace 10 -> 8/12 without a fidelity run.
- Look change: on-scale **No**; off-scale **Yes**.

### DS-A-3 Font sizes off the type scale (37 declarations)
- Scale in tokens.json: 11, 12, 13, 14, 15, 16, 20, 24, 34, 40. Off-scale found: 18px (9: decide.css:8,65; exceptions.css:54; projects.css:57; response.css:103; setup.css:8; start-work.css:38; work-item.css:144,205), 22px (7: month-end.css:52; my-work.css:139; projects.css:107; setup.css:71; start-work.css:41; work-item.css:257; workspace.css:57), 17px (5: decide.css:212,230,266,274; work-item.css:164), 10px (5: decide.css:243; floor.css:19; overview.css:64; work-item.css:228,275), 26px (4), 36px (2), 32px (2), 28/30/33px (overview.css:18; my-work.css:112; work-item.css:250).
- Rule: README "Text styles: page-title, drawer-title, panel-head, body (body-phone 15 on phones), hint, tag, eyebrow, label ...". 10px is below the smallest style (`label` 11px).
- Fix: map each to the nearest named text style; add text-style classes (`psl-t-hint` etc.) generated from tokens.json so features stop writing `font-size`.
- Look change: **Yes** (small).

### DS-A-4 Line heights as raw values (113 declarations)
- 24 `normal`, 19 `1.3`, 10 `1.5`, 9 `1.08`, plus px values 14-20 and ratios 1.05-1.7. Examples: `work-item.css:27-28,39,60-62,285-288,324-326,354-355,365,374-376,391`, `alerts.css:62,68,86`, `shell.css:76`.
- Rule: every text style has a fixed line height (body 21, hint 18, tag 17, label 14, panel-head 18, page-title 37).
- Fix: come with DS-A-3 (text-style classes). Look change: **Maybe**.

### DS-A-5 Letter spacing outside 0.06em (24 declarations)
- `.04em` (decide.css:86; my-work.css:61,120; projects.css:58; response.css:19; work-item.css:328), `.08em` (work-item.css:143), `.1em` (work-item.css:164), `.02em` (work-item.css:33), explicit `0` / `normal` overrides of the bundle (decide.css:243; setup.css:13,41; rfp.css:94; work-item.css:275).
- Rule: README "mono ... uppercase labels at 0.06em tracking". 0.06em is the only tracking value in the system. `setup.css:41` removes it from a panel head on purpose.
- Fix: 0.06em for mono/uppercase labels, normal otherwise; delete the rest. Look change: **Yes** (subtle).

### DS-A-6 Heights/widths and target sizes as literals (208 declarations)
- Control heights written as `40px, 42px, 36px, 34px, 32px, 28px, 24px` instead of `--control-sm/md/phone/lg/xl`: e.g. `decide.css:139-140` (40), `my-work.css:107-108` (40), `response.css:143` (42), `work-item.css:321` (42), `workspace.css:75,93` (40), `setup.css:64` (40), `rfp.css:59` (40), `start-work.css:58` (28).
- Rule: tokens.json size note "Every touch target is at least 44px; 40px only in the top bar, dense toolbars and segmented options on desktop". Sizes `control-phone 48`, `control-lg 50`, `control-xl 54`.
- Fix: replace by tokens where the element is a control; see E-1 for the ones below 44px. Look change: **Maybe**.

### DS-A-7 Borders and rules: literals instead of `--rule-strong` / `--rule-thin`; non-system border widths
- 71 `border: 2px solid var(--...)`, 20 `border-top: 2px`, 16 `border-bottom: 2px`, 11+11 `1px` rules written as literals. Not in the system: `1.5px` (response.css:72,78,80; work-item.css:189), `2px dashed` (response.css:69,79,81; start-work.css:67 uses `--ink-subtle`).
- Rule: README "rule-strong (2px) border in ink"; tokens `rule-strong`, `rule-thin`. Dashed edge is specified only for FileUpload (dashed `ink`) and SampleLabel (1px dashed `waiting`).
- Fix: `var(--rule-strong)`/`var(--rule-thin)`; 1.5px -> 2px (or 1px). Look change: 1.5px **Yes** (hairline), rest **No**.

### DS-A-8 Radii
- `features/alerts/alerts.css:60` `border-radius: 2px` (literal of `radius-sm`); `styles/shell.css:75` `border-radius: 9px` on the bell badge; `alerts.css` grab handle `border-radius: 2px`.
- Rule: README "Corners are radius-none; buttons and tags take radius-sm"; CountBadge is "a count in a small square".
- Fix: bell badge square (`radius-none`), tokens for the rest. Look change: **Yes** (bell badge turns square).

### DS-A-9 z-index literals (24)
- 1, 5 (13 places), 10 (`projects.css:17`, `shell.css:19`), 20 (`shell.css:28`), 30 (`alerts.css:26`, `exceptions.css:24`, `my-work.css:48`), 40 (`alerts.css:20,49`, `start-work.css:20`). The two layers at 40 (alerts layer and start-work layer) are the same stacking level as each other.
- Rule: none in the system (gap). Fix: ask DS for a layer scale (sticky 5, pop 30, scrim/drawer 40, toast 50); then tokenise. Look change: **No**.

### DS-A-10 Motion: durations/easings not from the system, no tokens
- `alerts.css:51-56`: drawer and scrim `200ms ease-out` with its own keyframes. README: state changes 120ms cross-fade; station moves 240-320ms ease-out; bundle uses `120ms ease-out`. No 200ms exists.
- `features/floor/scene.ts` (token slide) and `overview/OverviewPage.tsx:21` read reduced-motion themselves.
- Fix: motion tokens (`--motion-fast: 120ms`, `--motion-station: 280ms`, `--ease-out`) in tokens.json; use in alerts drawer. Look change: **Maybe** (drawer timing).

### DS-A-11 Reduced motion handled in four places, not by the bundle alone
- `alerts.css:57-59` and `workspace.css:176-178` (`.ws * { transition: none; animation: none }`, a blanket rule), `floor/scene.ts:77`, `overview/OverviewPage.tsx:21` (JS). The bundle's block (`psl-bundle.css:483-487`) already covers pulses/spinners/button transitions.
- Rule: README Motion "Reduced motion: ... state changes cross-fade in 120ms".
- Fix: one rule; for the floor, counts without movement (already done) plus 120ms cross-fade. Look change: **No**.

### DS-A-12 Breakpoints that differ from `bp-phone` 720 / `bp-desktop` 1080
- `features/my-work/my-work.css:15` `max-width: 719px` (leaves 719.5px in no mode); `features/workspace/workspace.css:147` `max-width: 720px` (720px counts as phone here, desktop elsewhere); `styles/shell.css:100` `max-width: 759.98px`, `shell.css:90` `1279.98px`, `shell.css:115` and `work-item.css:218` `379.98px`; `start-work.css:13`, `shell.css:57,94`, `work-item.css:82,174,183,331,370` use 1079.98/1080 correctly. `work-item.css:248` etc. fine.
- JS copies of the phone query: `PHONE_QUERY = '(max-width: 719.98px)'` appears in **7 files** (see DS-C-Hooks); `DrawerFrame.tsx:10` uses `(min-width: 720px)`.
- Rule: tokens `bp-phone 720px`, `bp-desktop 1080px`; README "below bp-phone (720px) the top bar becomes the phone bar".
- Fix: 720 and 1080 only; 379.98/759.98/1279.98 need a design ruling (they exist to fit specific boards). One `useIsPhone()`. Look change: **Maybe** (719/720 edge, narrow-desktop layouts).

### DS-A-13 Font families and weights
- Families: all `font-family` values use the three variables. No stray fonts. Inherit-resets at `work-item.css:337,354`, `overview.css:61`, `decide.css:113,162` are fine.
- Weights: 400/500/600/700/800 only, all inside the system. 53 uses of `600` for body-strong, matching `body-strong`.
- Archivo is self-hosted as "Archivo" with the width axis (`styles/fonts.css`); README asks for Google Fonts load: equivalent. No finding.

### DS-A-14 Opacity / shadows
- Shadows: only `inset` hairlines (`decide.css:128`, `response.css:78-80`, `work-item.css:228`) and `box-shadow: none`; no custom drop shadows. `color-mix(...)` is used in `my-work.css:104` and `alerts.css:33` (tinted mixes of tokens, not tokens).
- Rule: README "panels on the page never cast a shadow"; tints come from tokens (`signal-tint`, `action-tint`).
- Fix: replace the two `color-mix` values with a token tint (`action-tint` border, `signal-tint`). Look change: **Yes** (subtle).

### DS-A-15 Inline styles
- Only nine `style={{ width: '90%' }}`-style skeleton widths: `shell/FrameStates.tsx:14-16`, `my-work/MyWork.tsx:329-331`, `start-work/LineChooser.tsx:41-43`. `features/floor/scene.ts:373` sets `transform` per label (legitimate).
- Fix: one `<LoadingRows>` component (DS-C-Loading). Look change: **No**.

---

## B. Colour meaning

(Orange = a person must act; blue = buttons/links/agent or processing work; green = verified; amber = waiting on someone else + sample/test; grey = closed/n-a/info; "a state has exactly one colour everywhere".)

### DS-B-1 "Effect uncertain" has two colours (and two names)
- `features/work-item/labels.ts:27` `effect_uncertain` -> amber (`waiting`), `features/exceptions/labels.ts:6` -> amber with the text "SEND UNCERTAIN"/"Send uncertain", `features/overview/lines.ts:32` `uncertain` -> orange (`person`), `features/workspace/labels.ts:25` `uncertain` -> amber.
- Rule: StateTag README table: orange examples "Action needed, Owner needed, **Effect uncertain**"; amber "Waiting on client, Awaiting reconciliation". README state list says "Effect uncertain".
- Fix: one StateTag map; "Effect uncertain" orange everywhere (it needs a person to reconcile). Look change: **Yes** (work item, exceptions, overview).

### DS-B-2 "Restricted" and "stopped" differ between overview and workspace
- `overview/lines.ts:33` `restricted` -> orange, `workspace/labels.ts:27` `restricted` -> neutral. `stopped` -> `person` in both (OK per StationTrack: stopped = held with a reason, dashed `signal-ink`).
- Rule: neutral is "not applicable / information"; restricted access is information. Fix: neutral. Look change: **Yes**.

### DS-B-3 Agent step "done" is green in one place, blue in another
- `work-item/labels.ts:63` `AGENT_TAGS.done` -> green `psl-tag--done` (tag "DONE"); `rfp/FollowupCard.tsx:48` -> blue `psl-tag--agent` "DONE".
- Rule: AgentChecklist README "a WORKING or DONE tag"; blue = agent work; green = verified output. An agent's DONE is not a verified output.
- Fix: DONE on an agent card is blue (agent); keep green for Verified. Look change: **Yes**.

### DS-B-4 Processing station tinted amber (waiting) instead of blue
- `features/work-item/work-item.css:110-111`: `.work-state--processing ... .psl-station--agent, ... .psl-fact--current { background: var(--waiting-tint) }`; also the `ready` board tints the agent station orange (:110).
- Rule: StationTrack README "Current, agent or service: action-tint, blue edge = processing"; StateTag "blue = Processing".
- Fix: remove both overrides, rely on `.psl-station--agent`. Look change: **Yes** (SCR-02 processing/ready boards; check against the boards).

### DS-B-5 Blue used for non-agent surfaces
- `features/setup/setup.css:40-41,106`: Setup rule panels and the template upload panel get an `action` border and a solid blue head (`.setup-page .setup-panel__head`).
- `features/workspace/workspace.css:16-18`: `.ws-form` (a person's step form) gets a blue border and head; only `.ws-section--suggestions` (agent suggestions) should.
- `features/work-item/work-item.css:134`: `.work-agentpanel` fills with `mascot-chidi-tint` while keeping an action border (mascot colours are identity only, README Mascots "Colour rule").
- Rule: README "action (blue) ... buttons and links, and everything agents do ... A blue tag always means agent or processing work"; panels sit on `steel` in `surface` boxes with `ink` border, decision header orange.
- Fix: setup/step forms = standard `psl-panel` (ink border); keep blue for agent panels only. Look change: **Yes**.

### DS-B-6 Approve forced green
- `features/workspace/workspace.css:33-34` colours every non-secondary, non-reject button in `.ws-decide` `verified` green.
- Rule: Button README: Primary (blue) = Approve; Confirm (green) = "recording that something is verified or complete (Mark verified, Accept handover)". `DecidePanel.tsx` uses the right kind.
- Fix: remove the override, pick `psl-btn` (Approve) or `psl-btn--confirm` per step kind. Look change: **Yes**.

### DS-B-7 Amber used for "changed" and "severity"
- `decide/decide.css:164` changed rows get `waiting-tint` (amber means waiting on someone else); `decide.css:7` `.decide-changed` uses `signal-ink` for "changed" text.
- `workspace/workspace.css:25-28,82-83` severity: high orange, medium amber; and `ws-word--status-now` is amber in the checklist (:25) but blue in the words (:84).
- Rule: README "Priority ... never a status colour"; "waiting amber is for waiting on someone else".
- Fix: "changed" = neutral emphasis (bold or `neutral-tint`); severity = neutral tag with the mono marker (■■■ high); "now" = blue (agent) or orange (person) by actor. Look change: **Yes**.

### DS-B-8 Orange for things that are not "a person must act"
- `alerts/alerts.css:33` unread rows tinted `signal-tint`; `alerts/NotificationsPage.tsx:295` "NEW" tag is `psl-tag--person`; `alerts.css:86` Needs-you tab count in `signal` (acceptable: it counts items needing the person, see DS-C-CountBadge).
- `decide/decide.css:115` `.decide-strip__box--waiting` ("waits for" box) is orange (`signal-tint`), the word says waiting -> amber.
- `setup/RulesView.tsx:45` "HOLDS WORK" orange tag; `setup/DeliveryRulesView.tsx:58`, `FinanceRulesView.tsx:42` "NOT SET" orange but `setup.css:34,76` styles the same state amber; `clients/ClientsList.tsx:45` "Billing contact missing" orange (OK: setup needed).
- Fix: unread = bold + neutral dot; NEW = neutral; waiting box amber; NOT SET = one colour (orange "Setup needed" if it blocks, amber "Unknown" otherwise). Look change: **Yes**.

### DS-B-9 Green for non-verified facts
- `clients/ClientsList.tsx:43` "Set" tag is `psl-tag--done` (green) and `clients.css:51` `.clients__status` green for "saved"; `decide/decide.css:29` `.decide-banner--success` green for "decision recorded".
- Rule: green is for verified outputs / "done or verified". A recorded decision is not a verified output (`Approving does not send the invoice`).
- Fix: "Set" -> neutral; saved status -> success callout (green tick is allowed in Callout); decision-recorded banner -> Callout success (the component's job is "a fact was recorded"). Look change: **Yes**.

### DS-B-10 Custom amber boxes for test templates
- `work-item/work-item.css:189,204`, `WorkItemOverview.tsx:542` ("TEST TEMPLATE" in a solid 1.5px amber box and plain amber text) and `setup/TemplatesView.tsx:208` (`psl-tag psl-tag--waiting`).
- Rule: SampleLabel README "Amber, dashed edge, mono caps, so it never reads as a state". Use `.psl-sample`. See DS-C-SampleLabel. Look change: **Yes**.

### DS-B-11 Same Kind of tag, differing families by file (summary)
- Stopped -> `person` everywhere (consistent). Cancelled -> neutral (consistent). `RfpFrame` `statusTone` (`rfp/labels.ts:26-28`): deadline/pending/unknown amber, won green, others neutral: "deadline" is a person-must-act state; "won" is not a verified output (use neutral or an info Callout). Look change: **Yes**.

### DS-B-12 Month-end "facts" strip uses facts colours for task counts
- `finance/month-end/month-end.css:13-16` fills the DONE cell solid `verified` green (`monthend-cell--done`), WAITING amber, IN PROGRESS `surface`/`ink-subtle` (the "not yet earned" look). Green means a verified output; a count of finished tasks is not one, and in-progress work (agent/processing) is shown as "not yet".
- Rule: FactsStrip (earned = ink, current = signal-tint, not yet = surface/ink-subtle, verified = verified fill); blue = processing.
- Fix: a count strip with neutral boxes and tag-coloured numbers, not FactsStrip colours. Look change: **Yes**.
- Also `ProjectJourney.tsx:45-47` marks "waiting on people" and "stopped" as the current fact (orange); a project summary, not the six facts. See DS-C-26.

---

## C. Components

There are **no shared components**: every count below is the number of hand-written copies in `frontend/src`. "Spec" is the folder in `design/system/project/components/`.

| # | Component | Copies / where | Divergences (markup, states, keyboard, focus, announcements) |
|---|---|---|---|
| DS-C-1 | **Button** | 112 lines with `psl-btn` across 30+ files; no wrapper | (a) `psl-btn--sm` (40px) used in 27 places that are not the top bar/dense toolbars: ClientsList:158, DecideView:42, DecidePanel:104, ProofField:33, ResponseView:79, ReconcilePanel:181, CaughtUp:204, MyWork:430,442, ProjectsList:381,393, TemplatesView:196, ExceptionsList:260, SetupFrame:113, NotificationsPage:207,219, OutcomeView:52, FollowupCard:132,150, RecordPicker:177,208,218, LineForm:209 (retry and show-more buttons are mostly "Try again"/"Show more"). Spec: control-sm "only in the top bar and dense toolbars". (b) Busy state: only `LineForm.tsx:259-266` renders the three squares (`psl-busy`) and `is-busy`; others use `disabled` + text (`ClientsList:152`, `BillingContactForm:239` `disabled={busy}`, ExceptionsList:260, WorkItemHistory:235) or only `aria-busy`. Spec: "three small squares ... cannot be pressed twice". (c) Disabled: 46 `disabled`/`aria-disabled`, only 12 `aria-disabled`. Spec "Prefer an enabled control that explains what is missing"; reasons written next to disabled buttons are inconsistent (`workspace/Steps.tsx:45,72` does it right). (d) Hand-rolled button-lookalikes: `alerts-close` (alerts.css:63, 2px ink box, 32px), `shell-menubutton`, `shell-bell`, `setup-linkbtn` (`all: unset` reset, setup.css:103), `my-work__linkbutton`, `projects__linkbutton`, `work-disclosure`, `alerts-open--pri`, `resp-chip__remove`. (e) `<a class="psl-btn">` only for navigation: OK (DecideStates, WorkItemOverview). Look change: sm->md **Yes** (+4px height). |
| DS-C-2 | **Callout** | 70 callouts in 34 files | (a) 18 have **no icon** although the spec says "a tinted box with a leading icon": AlertSettingsPage:163,168,173,178; NotificationsPage:217; BillingContactForm:179; ClientsList:156; MyWork:440; ProjectsList:391; DecideStates:321,441; ReconcilePanel:187; OutcomeView:126; Workspace:28,244; LineChooser:28; WorkItemOverview:596. (b) Wrong `role`: spec says only **Problem** is `role="alert"`; **16 warning callouts** carry `role="alert"` (e.g. DecideView:26,36; DecideStates:321,433; ResponseView:59,104; ReconcilePanel:174; Workspace:251,265; SetupFrame:103; AlertSettingsPage:168; FollowupCard:19; OutcomeView:33; LineForm:69,89); **4 problem callouts have none** (ClientDetail:84, MyWork:440, ProjectsList:391, NotificationsPage:217); success without `role="status"`: Workspace:244 (wrapped in a live region, OK). (c) Element: `<p>` in DecidePanel:95,110, ReconcilePanel:187, Workspace:244, Sections:469, WorkItemOverview:596, RecordedView:130 vs `<div>` elsewhere; `<h2>` inside a callout DecideStates:321. (d) Callouts that carry buttons (retry) : DecidePanel:101, NotificationsPage:217, ClientsList:156, MyWork:440, ProjectsList:391, ExceptionsList - each wraps `<span>` + `psl-btn--sm`, with five local classes (`*-morefail`, `decide-retry`, `resp-retry`). (e) A parallel box: `clients.css:48` `.clients__notice` (waiting-tint box) is a callout reimplemented; `decide.css:182` overrides `.decide-next` to blue and `:287` recolours text. (f) Icons: `WarningIcon` (shell/icons.tsx), per-feature `InfoIcon` x3, `TickIcon` (setup), `CheckIcon` (response). Look change: icon added **Yes**. |
| DS-C-3 | **StateTag / tags** | 25 `psl-tag` usages in 20 files; tag-class tables in 8 files (`work-item/labels.ts:19-31,62-66,135-139`, `workspace/labels.ts:20-31`, `exceptions/labels.ts:5-11`, `overview/lines.ts:25-39`, `rfp/labels.ts:25-28`, `finance/month-end/model.ts:110`, `floor/scene.ts:235,567`, `my-work/model.ts`) | Same states, different words/colours (DS-B-1..3); text case inconsistent: STATE_TAGS are sentence case, exceptions/no-access/test tags are CAPS in source ("NO ACCESS" clients/ClientStates:8, projects/ProjectStates:9, work-item/WorkItemStates:38, month-end/MonthEndStates:8; "SEND UNCERTAIN", "BLOCKED"). Local overrides: `setup-tag`, `rfp-tags .psl-tag` (rfp.css:10 radius none, line-height normal), `work-state` (uppercase, .02em, 5px 10px - work-item.css:33), `work-who .psl-tag` (10px mono, inset hairline - :228), `floor__line .psl-tag` (10px - floor.css:19), `work-tag--outline` for FACTORY (a sixth style, :229). Priority tag with ■■■ marker: **not implemented anywhere** (grep for `psl-prio` finds none). Look change: **Yes**. |
| DS-C-4 | **CountBadge** | `psl-badge` x11 (MyWork:485, filters) + `alerts-tabcount` (alerts.css:86, AlertsDrawer:175) + `shell-bellbadge` (shell.css:74-77) + `shell-bellchip` (shell.css:78-80) + plain `{count}` text (`setup-counts`, `ws-count` uppercase text, TemplatesView `{rows.length} SHOWN`) | Three custom badges with own colours/radius (9px radius, DS-A-8). Unknown count renders `'–'` (MyWork.tsx:485); spec "Zero shows 0 ... people can tell 'none' from 'not loaded'", and Unknown is written Unknown. Look change: **Yes**. |
| DS-C-5 | **Panel** | 28 `psl-panel`; local `Panel` in `rfp/RecordedView.tsx:27`; custom panel shells: `.work-statepanel`, `.work-agentsec`, `.work-agentpanel`, `.setup-panel`, `.ws-section`, `.resp-reconcile`, `.resp-agent`, `.projects__agent`, `.decide-agent`, `.shell-errorcard` | Head styles differ: `decide.css:86` 16px/stretch/.04em, `work-item.css:164` 17px/.1em, `work-item.css:143` 15px/.08em, `alerts.css:21` 14px, `response.css:107` 15px amber fill, `setup.css:41` blue fill. Spec: `panel-head` 14/18 uppercase 800. Agent card is built 5 times (work-item `psl-agent` x2, rfp `psl-panel--agent`, response `resp-agent`, projects `projects__agent`, decide `decide-agent`). Look change: **Yes**. |
| DS-C-6 | **TextField / TextArea** | about 28 inputs/textareas, 9 files with `aria-invalid` | `<label>` wiring is by wrapper `<label class="resp-field">` (response, rfp) vs `htmlFor` (my-work) vs `Field` helper (`rfp/OutcomeForm.tsx`) vs hidden `.xx-sr` label; `StepForm.tsx:119` input has **no `psl-input` class** (own `ws-money`); `IntakeField.tsx:104` date input no class. Error pattern: `psl-error` with `aria-describedby` in 6 files; `setup/SetRulePanel.tsx:230,243` uses `is-error` + `aria-invalid` **without** `aria-describedby`; `ResponseForm.tsx:55` has none; `StepForm.tsx:163` has `role="alert"` on an inline error (others rely on a summary callout). Spec Error: "`signal` border ... message with a warning icon under it": the warning icon is absent from every `psl-error` use. Look change: **Maybe**. |
| DS-C-7 | **Select** | 9 native `<select class="psl-input">` (AlertSettingsPage:254,274; MyWork FilterPanel:114,132,151; ResponseForm:39; SetRulePanel:204; WorkItemHistory:163; IntakeField:125) vs 1 custom listbox `start-work/RecordPicker.tsx` (role="listbox", own keyboard) | Native selects restyled per feature (`my-work.css:39` draws a custom ▾ with gradients; others show the browser arrow). Spec: `psl-select` trigger + `psl-listbox`, `shadow-pop`, `psl-chev`. RecordPicker uses a text glyph `▾` (line 142) instead of the chevron icon. Look change: **Yes** (if natives are replaced). |
| DS-C-8 | **DateField / MoneyField** | Native `<input type="date">` x3 (OutcomeForm:146, SetRulePanel:230, IntakeField:104); money inputs: StepForm.tsx:118-119 (`ws-money`, inline ₦ span), OutcomeForm:57 (plain text field, no ₦, not mono), TeamInputForm:39 (number, "person-days") | No `psl-cal`, no `psl-input--money` anywhere. Spec: MoneyField mono with ₦; dates "17 Nov 2026". Look change: **Yes**. |
| DS-C-9 | **Checkbox / Radio** | Checkbox: `psl-check` in FilterPanel:100; bare/custom in ResponseForm:123, TeamInputForm:65, OutcomeForm:75, SetRulePanel:216, Workspace:198 (`ws-check`), AlertsFilterPanel:64; Radio: `resp-pill`/`resp-option`/`resp-segopt` custom (response.css:55-66,113), ExceptionsFilter:52, AlertsFilterPanel:58, ReconcilePanel:145, LineChooser:136 | Only 1 of 9 checkboxes uses `psl-check`; the custom ones each re-implement focus ring (`response.css:59-66,113`). `alerts/AlertSwitch.tsx` (`role="switch"`) has no spec counterpart (Checkbox/Toggle gap in the DS). Look change: **Maybe**. |
| DS-C-10 | **Segmented** | 8: MyWork:410, ProjectsList:361, ExceptionsList:240 (rows per page), WorkItemHistory:45 (filter), OverviewPage:189 (View), IntakeField:241, response/Segmented.tsx:34 (its own component), ResponseForm:81 (pill variant) | The three "Rows per page" bars are byte-for-byte copies with the same arrow-key handler (MyWork:295, ProjectsList:295, ExceptionsList:167); the others differ: `Segmented.tsx` handles Left/Right/Up/Down, `IntakeField.tsx:232` similar, OverviewPage:121 similar. **No Home/End anywhere** (grep: zero). Spec: counts as badges not "· N"; "Every option stays on one line". "Rows per page" itself conflicts with ShowMore ("No numbered pages"). Look change: **No** (refactor). |
| DS-C-11 | **Tabs** | `role=tablist`: MyWork:467, ProjectTabs.tsx:22, ProjectsList:420, AlertsDrawer:160 (custom `alerts-tab`, not `psl-tab`); link-tabs with `aria-current`: SetupFrame:37, WorkItemView:128,220, RfpFrame:63 (includes non-interactive `<span class="psl-tab">` RfpFrame:24,32) | Two ARIA patterns for one visual; arrow-key handlers copied 4 times (MyWork:287, ProjectTabs:14, ProjectsList:306, AlertsDrawer:127); no Home/End; tab heights overridden below 44px (`work-item.css:43` 28px, `:315-316` 24px) - E-1. Look change: **Yes** (heights). |
| DS-C-12 | **Menu / dropdowns / SplitButton** | Phone menu `PhoneBar.tsx:74` (`psl-pop psl-menu`); account menu none; SplitButton `start-work/StartWorkButton.tsx:43-70` (`sw-split`, arrow `aria-haspopup="dialog"` opens a drawer, not a Menu) | There is exactly one `psl-menu`. Menu spec: Esc returns focus to the opener - `PhoneBar.tsx:39-41` does it; SplitButton spec: "The menu is the Menu component" - the arrow opens the line chooser drawer (CMP-23 says menu). Look change: **Maybe**. |
| DS-C-13 | **SearchField / ListToolbar** | Search: MyWork:496, ExceptionsList:329, NotificationsPage:250, ProjectsList:449, TemplatesView:240, LineChooser:114, RecordPicker:154; Filter button + sheet/pop: MyWork (FilterPanel.tsx:174,194), ProjectsList:162, ExceptionsFilter:63,87, AlertsFilterPanel:82,106, NotificationsPage:158 | Each list re-assembles `psl-toolbar`/`psl-search` with its own hidden label class (`my-work__sr`, `exc-sr`, `setup` uses `aria-label`) and own debounce; no clear-search button (`psl-search__clear` unused); no "Clear all" chip row in setup/clients lists; result count formats differ (`shownText`, `allShowingText`, `{n} SHOWN`). Filter panel: 4 copies of popover + sheet (Esc/outside-click handlers copied: FilterPanel:58-72, ProjectsList:147, ExceptionsFilter:32, AlertsFilterPanel:37); **none traps focus or sets `aria-modal`** while the phone sheet sits over a scrim; focus return to the Filter button is hand-coded per page (MyWork:255,268; ExceptionsList:154; ProjectsList:314; NotificationsPage:141); `role="dialog"` with `aria-label="Filter"` in three, `"Filter projects"` in one. Look change: **No** (behaviour). |
| DS-C-14 | **FileUpload** | `response/ProofField.tsx:92-` and `setup/ProofField.tsx:37-` (two files of the same name), `setup/TemplateUploadPanel.tsx:65` (`setup-fileinput`), inline svg paperclip `ProofField.tsx:21`; `useEvidenceUpload.ts` and `setup/useTemplateUpload.ts` | Two ProofField copies with different states: response has chip + remove (`resp-chip__remove` 24px target), setup uses visually hidden `<input>` (`setup-sr`); drop-zone dashed borders drawn 3 ways (`response.css:69,79,81`, `setup.css:53`, `start-work.css:67` in `--ink-subtle`); "restricted" state absent. Spec: dashed `ink`, solid blue on drag-over, 10 MB / PDF PNG JPG EML stated in the zone. Look change: **Maybe**. |
| DS-C-15 | **Drawer / BottomSheet / Dialog** | Drawer: `start-work/DrawerFrame.tsx` (500px via `psl-drawer`, switches to `psl-sheet` under 720), `alerts/AlertsDrawer.tsx:139-155` (own `alerts-drawer`, 420px); sheets: three filter sheets (above); no Dialog | Two drawer implementations: alerts 420px vs spec 500px (alerts.css:52), own scrim element (`alerts-dscrim`) and 200ms animation vs DrawerFrame's `psl-scrim`; both trap Tab by hand (DrawerFrame:64-78, AlertsDrawer:64-74) and use `aria-modal` (DrawerFrame:90, AlertsDrawer:145) but filter sheets do not. Alerts close = text button "Close" 32px (alerts.css:63) vs spec close icon button. Focus return: `AppShell.tsx:99-105` for alerts, `StartWorkButton.tsx:36` for start work. Look change: **Yes** (alerts drawer width and close button). |
| DS-C-16 | **Toast / Tooltip** | none | Spec says "done (closes and shows a toast)" for the Drawer; the frontend shows inline callouts/`role="status"` lines instead (`Workspace.tsx:242-248`, `ReconcilePanel.tsx:187`, `AlertSettingsPage.tsx:163`). Native `title=` tooltip on a time (`ExceptionsList.tsx:66`); keyboard/touch users cannot read it. Look change: **Yes** when toast is introduced. |
| DS-C-17 | **Table** | 12 `<table>`: 9 with `psl-table` (ClientsList:52, WorkRows:39, ProjectsList:69, Sections:204, RulesView:83, TemplatesView:253, DeliveryRulesView:44, WorkItemHistory:201, ExceptionsList:51, AlertSettingsPage:217), bare `<table>` in `WorkItemOverview.tsx:501`, custom `monthend-table` in `finance/month-end/MonthEndView.tsx:92` | Month-end table and cards do not use the bundle at all; sorted-column arrow and select-all (spec) absent everywhere; empty state "a sentence in the body" present in most; right-aligned mono amounts: month-end abbreviates (`₦4.7M`, `finance/month-end/model.ts:63`) - spec "two decimals". Look change: **Yes** (month-end). |
| DS-C-18 | **ShowMore** | 9: MyWork:404, ProjectsList:355, ExceptionsList:266, WorkItemHistory:231, ClientsList:150, SetupFrame:109, NotificationsPage:204, RecordPicker:214, workspace/Sections.tsx:384 (inert) | Wording: "Show more", "Show more entries / + n earlier entries", "N shown", "All N showing"; spec "Show 50 more" and "All 74 showing". "ROWS PER PAGE" bars (MyWork:408, ProjectsList:359) contradict "No numbered pages" (recorded as D-PAGING r2). `clients/ClientsList.tsx:152` shows the label "Loading…" inside the button without squares. Look change: **Maybe**. |
| DS-C-19 | **Loading / Empty / Error** | `psl-loading` x6 (FrameStates:18, MyWork:333, StartWorkDrawer:43, RecordPicker:170, LineChooser:45, OverviewPage:253); `psl-empty` x28; error cards: `shell-errorcard`, `AlertsLoadError` (AlertParts.tsx:68), per-feature `*-retry` callouts | Error is a Problem callout with Retry (spec) in some places, a warning callout in others (DecideView:36, ResponseView:59, OutcomeView:33, FollowupCard:19 are warning + `role="alert"`), and an errorcard (shell.css:38). Skeleton rows hand-written 3 times with inline widths (DS-A-15). Look change: **Maybe**. |
| DS-C-20 | **Icon / IconButton** | Icons: `shell/icons.tsx` (Menu, Warning), `my-work/icons.tsx` (Search, Filter, Close), `response/icons.tsx` (Check, Info), `setup/icons.tsx` (Info, Paperclip, Tick, Search), `work-item/InfoIcon.tsx`, inline `<svg>` in 8 other places (ProofField:21, AlertsBell:19 (24px viewBox, 20px), FollowupCard:56, StartWorkButton:12,57, IntakeField:167, RecordPicker:150, LineForm:35, LineChooser:110) | Four duplicate `InfoIcon`s and two `SearchIcon`s; text arrows used in place of the Back icon: `← label` (PhoneBar:65, AlertSettingsPage:119, NotificationsPage:236, MonthEndView:42), text `▾` (RecordPicker:142), `✓` char (WorkItemOverview:157), `×` char (DrawerFrame close). README: "The set is in the Icon component ... Icons support words". Icon-only buttons all carry `aria-label` (checked, 9 of 9): good. Look change: **Maybe** (glyphs differ). |
| DS-C-21 | **Link / Breadcrumb** | `psl-link` x8 plus hand-made link-buttons (`my-work__linkbutton`, `projects__linkbutton`, `setup-linkbtn`, `work-disclosure`, `decide-trail a`); `psl-crumb` x12 (ClientDetail:74, DecisionContent:53, ResponseView:41,50, ProjectJourney:183, SetupFrame:35, WorkItemView:62,65,166,176, OutcomeView:92, FinanceRulesView:53) | The crumb is a `<p>` in 11 places, `<ol>` in one (WorkItemView:166); `aria-current="page"` on a span (ClientDetail:75) vs `"location"` on an li; the same crumb's separator is typed "/" text in 4 files; `psl-crumb` is also used for eyebrows (SetupFrame:35, WorkItemView:62). Some `<a href>` (MonthEndView:41, full reload) instead of `next/link`. Look change: **No**. |
| DS-C-22 | **Disclosure** | `psl-disclosure`: 0 uses; hand-rolled `work-disclosure` button x2 (WorkItemOverview:302,550, work-item.css:122) and more in Sections.tsx | Spec: `<details>/<summary>` with a triangle. Look change: **Yes**. |
| DS-C-23 | **ValidationSummary** | 0 | Forms use a problem callout (LineForm:54, StepForm:276, AlertSettingsPage:173) with focus moved to it, not a list of links; no "N things to fix". Look change: **Yes**. |
| DS-C-24 | **AgentChecklist** | `work-item/WorkItemOverview.tsx:151,178,191,359` (`psl-agent`, `psl-steps`), `rfp/FollowupCard.tsx:33-53` (a second implementation using `psl-panel--agent`), `workspace/Workspace.tsx:25` (`AgentNote` with `ws-agentnote`), `response.css:24` `.resp-agent`, `projects.css:79` `.projects__agent`, `decide.css:78` `.decide-agent`, `my-work.css:101` `.my-work__free` | At least 7 implementations of "blue card with avatar and task". Only two render steps; step states (`stopped`, `wait` dashed amber) exist only in the work-item copy; "Ask Tola" footer present only in the work-item copy; Reduced motion pulse is the bundle's. `stepKind()` and `STEP_WORDS` ("Done", "In progress", "To do") live in `work-item/labels.ts:70-90`. Look change: **Yes**. |
| DS-C-25 | **Avatar** | `avatarClass()` in `work-item/labels.ts:92-96` (used in decide, work-item), `alerts/AlertParts.tsx:15-18`, `my-work/WorkRows.tsx:22`, `my-work/CaughtUp.tsx:185`, `projects/ProjectJourney.tsx:109`, `start-work/LineChooser.tsx:29`, `overview/OverviewPage.tsx:56` | Six ways to place the same mascot: `<Image>` with different `alt` (""/descriptive), sizes 20/28/36/40 (spec 20/32/40), classes built by string; `psl-avatar--dark` for people unused (people initials not rendered anywhere). Look change: **Maybe** (28/36 -> 32/40). |
| DS-C-26 | **FactsStrip** | `work-item/WorkItemOverview.tsx:88` (the real one), `projects/ProjectJourney.tsx:51` (own `FactsStrip`, 4 counts), `decide/DecisionContent.tsx`/`decide.css:107-116` (`decide-strip` boxes), `finance/month-end/MonthEndView.tsx:55` (`monthend-strip`) | Facts strip in the spec has six facts; the other three are metric strips under the same name; `decide-strip` is ink/boxes with waiting orange (DS-B-8). Unknown facts: `psl-fact--unknown` used in work-item and projects, but month-end uses "waiting" cell tone. Look change: **Yes**. |
| DS-C-27 | **StationTrack / MiniStationBar** | StationTrack: `WorkItemOverview.tsx:111` only (3 call sites + a phone/list variant via `work-track--list`, `work-item.css:331-381`, which re-colours every station kind); MiniStationBar: `decide/DecisionContent.tsx:212`, `my-work/WorkRows.tsx:27,60`; `overview.css` squares (`overview__sq`); `floor` chips | The mini bar markup is copied twice (decide, my-work) with different word formats; the work-item CSS overrides `.psl-station--*` colours 14 times (`work-item.css:338-343,356-360,379-381`) - the bundle is not trusted as the source. Look change: **Yes**. |
| DS-C-28 | **DecisionPanel / PhoneActionBar** | `decide/DecidePanel.tsx` (the DS shape), `work-item/WorkItemOverview.tsx:563` (own variant with `you_can_act`), `workspace/Workspace.tsx:313` (`ws-decide`), PhoneActionBar `psl-actionbar` x5 (DecidePanel:115, ResponseView:175, ReconcilePanel:191, ResponseForm:152, OutcomeForm:237) | Three decision panels; the phone panel head is hidden with `position:absolute` clipping in 4 files (`decide.css:224,227`, `response.css:139`, `work-item.css:261,265`, `workspace.css:159`, `rfp.css:95`) - same trick pasted. Header font size 16/17/15 (DS-C-5). "What it does not do" line (`psl-doesnt`) exists in DecidePanel:150 only; the workspace panel has none. Look change: **Yes**. |
| DS-C-29 | **SampleLabel** | `shell/SampleLabel.tsx` (good, 14 call sites) + 3 hand-made "TEST TEMPLATE" (DS-B-10) | See DS-D-1, DS-D-2. |
| DS-C-30 | **SourceTag / DraftCard / ChatMessage / TopNav / WorkList** | `app/assistant/page.tsx` is a stub: **no ChatMessage, DraftCard, SourceTag, composer or suggestions** are built. TopNav: `shell/TopNav.tsx` uses `psl-nav`/`psl-navlink` (correct); WorkList: `my-work/WorkRows.tsx` (table + cards, not the single-link row the spec draws, `psl-row`/`psl-list` unused) | WorkList row is a `<table>` row with several links (`data-work-link`), spec "Whole row is one link". Look change: **Yes** for WorkList. |
| DS-C-Hooks | **Non-visual duplicates** | `usePhone` x4 (`response/usePhone.ts`, `work-item/usePhone.ts`, `alerts/useIsPhone.ts`, inline in MyWork:45-59, ProjectsList:35-51, ExceptionsList:23-33, OverviewPage:20, `overview/useMedia.ts`); visually-hidden CSS class x14 (`overview__sr`, `my-work__sr`, `clients__sr`, `exc-sr`, `alerts-sr`, `decide-sr`, `projects__sr`, `setup-sr`, `work-sr`, plus inline clip rules in 12 places); date formatters x9 (decide/format.ts, response/labels.ts:45, setup/format.ts:5, exceptions/labels.ts:19, alerts/model.ts:29, work-item/labels.ts:143, clients/labels.ts:14, projects/model.ts, month-end/model.ts:26); money formatters x6 (decide/format.ts:13, month-end/model.ts:63, workspace/labels.ts:84, clients/labels.ts:11, projects/model.ts:131, rfp/labels.ts:37) | None of the formatters writes the README formats ("17 Nov 2026", "14:30 WAT"): outputs include "12 Nov 16:40" (no year, no WAT), "14 Nov, 10:00", "11 Nov", "10:47". Look change: **Yes** (date text). |

Priority of C items by copies x divergence is in the build order at the end.

---

## D. Content rules

### DS-D-1 SAMPLE DATA label is switched off by default
- `shell/sample.ts:3`: `showSampleLabel = process.env.NEXT_PUBLIC_SHOW_SAMPLE_LABEL === '1'`, used by `SampleLabel` and `decide/DecisionContent.tsx:49`. Comment cites "design decision, 14 Nov 2026".
- Rule: README "Sample, test and mock content always carries a label"; SampleLabel README "every time it appears"; CMP-16 "instead of a banner once per session".
- Fix: ask the design engineer whether the 14 Nov decision supersedes the README; if yes record it in the DS README, else flip the default. Look change: **Yes** (labels reappear).

### DS-D-2 Sample/test/mock labels missing on screens that show seeded records
- `SampleLabel` is called only in clients, decide, my-work, projects, work-item. Not called in: exceptions (`ExceptionsList.tsx`), overview/floor, response (`ResponseView.tsx:5` comment: "No SAMPLE DATA tag: the boards draw none"), rfp, setup, alerts/notifications, workspace, finance month-end, start-work. `TEST TEMPLATE` is drawn in 3 hand-made ways (DS-B-10); `MOCK DELIVERY` is used nowhere although `ExceptionsList.tsx:280` and send receipts speak of sends.
- Fix: records carry `sample`; render `SampleLabel` in every list row/detail head; add the MOCK DELIVERY variant to the shared component. Look change: **Yes**.

### DS-D-3 State words outside the README list
- README list: Ready to continue, Processing, Waiting, Awaiting Finance decision, Owner needed, Setup needed, Action needed, Effect uncertain, Awaiting reconciliation, Verified, Cancellation requested, Cancelled.
- Found: "Send uncertain" (`exceptions/labels.ts:6`, README says Effect uncertain), "Blocked", "Follow-up needed" (exceptions/labels.ts:9-10), "HOLDS WORK" (`setup/RulesView.tsx:45`), "NOT SET", "Held", "Not applicable", "Uncertain", "Failed" (`workspace/labels.ts:35-52`), "Record pending", "Decision pending", "Outcome unknown" (`rfp/labels.ts:11,17`). Missing from the code: "Awaiting Finance decision" and "Cancellation requested" (STATE_TAGS at `work-item/labels.ts:20-32` has 11 contract states; those two are absent, check whether the contract lacks them).
- `Stopped: invoice follow-up needed` is allowed (CMP-05).
- Fix: map contract values to README words in one table; keep "Held", "Failed" only if the design engineer adds them to the list. Look change: **Yes** (words).

### DS-D-4 "Done" / "Complete" used as a state
- Station status text `done: 'Done'` (`work-item/labels.ts:47`), step words "Done" (`:81`, `workspace/labels.ts:35`), checklist "DONE" (`work-item/labels.ts:63`, `rfp/FollowupCard.tsx:48`), month-end summary cell "DONE" (`finance/month-end/MonthEndView.tsx:50`).
- Rule: README "Never invent synonyms such as Done or Complete for a state" (AgentChecklist spec allows a DONE tag on the agent card; the My work tab "Done" is in CMP-06).
- Fix: station = "Earned"/"Verified" (as `decide/DecideStates.tsx:138` already writes "Earned"); month-end cell "Verified"; keep DONE only on the agent card. Look change: **Yes**.

### DS-D-5 Facts strip uses "RECEIPT" and merges nothing, but month-end merges states
- `work-item/labels.ts:38-43` writes RECEIPT with a screen-reader completion (" RECORDED"); fine. `finance/month-end/MonthEndView.tsx:50-66` builds a strip titled "Facts earned" (`aria-label`) out of DONE / WAITING / IN PROGRESS counts: those are task states, not facts. Fix: rename aria-label and use a count strip (not FactsStrip). Look change: **No**.

### DS-D-6 "Unknown" rendered as dash or other words
- `my-work/MyWork.tsx:485` badge shows `'–'` when a count is unknown; `projects/ProjectsList.tsx:93` shows `'—'` when there is no next milestone; `decide/DecideStates.tsx:138` fact word `not_yet: '—'` (acceptable for "not yet", not for unknown); `projects/model.ts:50,118,131` writes "Not known" / "due not known" / "Not given" (`clients/labels.ts`), where the README says "Unknown". Unknown amounts elsewhere are right (`psl-unknown` in decide, workspace).
- Fix: Unknown tag (amber `psl-unknown`) for unknown; reserve "—" for not applicable. Look change: **Yes**.

### DS-D-7 Money and dates not in README format
- Money: `finance/month-end/model.ts:63-76` shows "₦4.7M" (rounded, no two decimals); `rfp/OutcomeForm.tsx:57` free text. README "amounts are mono with ₦ and two decimals, right-aligned in tables". Dates: no formatter shows the year plus "WAT" (see DS-C-Hooks); `work-item/labels.ts:150-155` "12 Nov 16:40"; README "17 Nov 2026", "14:30 WAT" in mono.
- Fix: one `formatMoney`, `formatDate`, `formatTime` and `<Money>`/`<When>` components. Look change: **Yes**.

### DS-D-8 Merged facts
- `ProjectJourney.tsx:45-47` shows "waiting on people" and "stopped" as counts in a facts strip together with "invoices verified": allowed as a project summary; no merged drafted/approved/sent chip was found. `WorkItemHistory.tsx:75` "Approved invoice v2 for ₦..." fine. No finding beyond DS-D-5.

### DS-D-9 Agent copy
- No agent text saying "decide/approve/send" was found in the strings I searched (agent roles in `AGENT_TAGS`, `FollowupCard`, `Workspace.tsx:25 AgentNote`); `rfp/FollowupCard.tsx:138` "doesn't send anything" is correct. The assistant page (where such copy would appear) is a stub, so this check should be repeated when it is built. `LineForm.tsx:136` "a ... decides" refers to a person's role (OK).
- `WorkItemOverview.tsx:596` next-step text is server-supplied; the client cannot guarantee it.

### DS-D-10 Technical ids secondary
- Most references use `psl-mono`. Exceptions: `work-item.css:138-142` and `decide.css` eyebrows put references in the 12px eyebrow before the title (`work-eyebrowline`, `decide-eyebrow`); `ProjectsList`/`WorkRows` show reference after the line in mono (correct). `AlertSettingsPage.tsx:178` prints "Reference {code} for support" in prose, acceptable ("never show a raw error code first" - it is second).
- Fix: none required; re-check on migration.

### DS-D-11 "What the action does not do" line missing
- Present: `DecidePanel.tsx:150`, `DecideStates.tsx:382`. Absent on the workspace decision (`Workspace.tsx:313-340`) and on RFP/response record buttons (spec Button "Pair a decision button with a line"). Look change: **Yes**.

### DS-D-12 Emoji / pictographs
- No emoji found in `.ts/.tsx`. Glyph substitutes for icons are listed under DS-C-20.

---

## E. Accessibility the system requires

### DS-E-1 Touch targets below 44px (and 40px used outside the top bar)
- `features/work-item/work-item.css:43` (tabs 28px), `:315-316` (tabs 24px on phone), `:320` (select 28px), `:406` (link 24px); `my-work.css:28` (text buttons 28px on desktop), `:34` (36px); `response.css:77` (chip remove 24px), `:28` (36px); `rfp.css:33` (24px "Unknown" button); `alerts.css:63` (close 32px), `:72` (28px); `floor.css:10` (chip 24px); `decide.css:79,214` (36/32px); `projects.css:81` (36px); `start-work.css:58` (28px); `shell.css:69,102` (36/32px controls); `.psl-chip button` and `psl-search__clear` are 28/36 in the bundle itself.
- Rule: README "Every touch target is at least space-7 (44px)"; tokens size note.
- Fix: raise to `--control-md` (on phones at least), or enlarge hit area with padding while keeping the visual; ask for a decision on dense desktop toolbars (the bundle itself permits 40px). Some of these are avatars/decorative (decide.css:79,214; start-work.css:58): confirm per element. Look change: **Yes**.

### DS-E-2 Focus
- Global rule `.psl :focus-visible` (`psl-bundle.css:14-15`) covers all `.psl` content; local overrides re-add rings correctly (setup, response, workspace, floor). Problem spots: `start-work.css:23` `.sw-panel { outline: none }` (programmatic focus only: OK), `workspace.css:135` removes the input ring but substitutes `:focus-within` ring (OK); `alerts.css:37,85` set `outline-offset` negative inside rows (matches inset rule). No failing case found. Dialog/sheet focus traps missing on the three filter sheets (DS-C-13). Look change: **No**.

### DS-E-3 Colour as the only signal
- `projects/ProjectJourney.tsx:82` colour dot is `aria-hidden` with the state tag text beside it (OK); `overview.css:35` station squares coloured, labels give counts (OK); `alerts.css:33` unread row differs by tint and bold weight (bold is a second cue, weak). Floor chips (`floor/scene.ts:164`) orange fill plus text em (OK). No blocking finding; the mini station bar (`my-work/WorkRows.tsx:27`) is always followed by words.

### DS-E-4 Contrast
- Token pairs follow the system's numbers. Check on migration: `response.css:107` white on `--waiting` (#8A5A00 on white about 6:1, OK), `alerts.css:86` white on `--signal` 11px (5.1:1, OK), `.work-invoice__test` text `--waiting` on white (#8A5A00, about 6:1 OK), but `--waiting` is used as text on `waiting-tint` only via `waiting-ink` elsewhere - `work-item.css:204` `color: var(--waiting)` on white is fine; `ink-subtle` on `surface-subtle` 5.1 OK. No failing pair found by reading; run an automated contrast check (axe) as part of the migration.

### DS-E-5 Reduced motion
- Covered (DS-A-11). `workspace.css:177` `.ws * { transition:none; animation:none }` is broader than needed (kills the busy squares' state cue too, though the label still says "Recording..."): replace with the bundle's rule.

### DS-E-6 Icon-only buttons
- All nine icon-only buttons have `aria-label` (AlertsFilterPanel:87, NotificationsPage:261, ExceptionsFilter:68, ExceptionsList:344, MyWork:511, ProjectsList:165,460, DrawerFrame:105, plus bell/menu/start-arrow). No finding.

### DS-E-7 Announcements
- `role="alert"` on warnings (16) causes assertive interruptions for non-critical states; problem callouts without a role (4: ClientDetail:84, MyWork:440, ProjectsList:391, NotificationsPage:217) are silent when a load-more fails. Sheet dialogs without `aria-modal`. `ExceptionsList.tsx:66` relies on `title=` for the full time. Look change: **No**.

### DS-E-8 Keyboard patterns
- Tabs/segmented: Arrow keys only, no Home/End (DS-C-10, DS-C-11); `RecordPicker.tsx:100-114` implements listbox arrows and Esc; native selects elsewhere. Menu items: `PhoneBar.tsx:84` ok. Look change: **No**.

---

## Summary by group

| Group | Findings | Look can change | Notes |
|---|---|---|---|
| A Foundations | 15 (A-1..A-15) | A-1, A-2 (off-scale), A-3, A-5, A-7 (1.5px), A-8, A-14: yes | 0 colour literals; main gaps are missing tokens (type, motion, z-index) |
| B Colour meaning | 12 (B-1..B-12) | all visible | B-1 (Effect uncertain), B-4 (processing amber), B-5/B-6 (blue/green misuse) matter most |
| C Components | 30 rows (C-1..C-30, plus hooks) | most | no shared layer; 7 phone hooks, 14 sr-only classes, 9 date and 6 money formatters |
| D Content | 12 (D-1..D-12) | words and labels visible | D-1 and D-2 hinge on a design-engineer ruling |
| E Accessibility | 8 (E-1..E-8) | E-1 yes | focus and icon labels already good; targets and announcements need work |

## Questions the design engineer must answer before the migration finishes

1. Are `tokens.json` additions allowed (text styles, motion, z-index, spacing 10/14/18/20)? Without them A-2 to A-5 and A-9/A-10 cannot be closed by "using a token".
2. Does the 14 Nov decision to hide SAMPLE DATA by default override the README (D-1)?
3. Is "Rows per page" (D-PAGING r2) a deliberate exception to ShowMore?
4. Which sub-44px desktop controls are acceptable dense toolbar items (E-1)?
5. Does the alerts drawer stay 420px, and is "Effect uncertain" orange (B-1) final?

## Recommended component build order (most copies and most divergence first)

1. **Foundations first (no visual risk):** `PageTitle`/text-style classes, `VisuallyHidden`, `useIsPhone`, `formatDate/Time/Money` + `<Money>`/`<When>`, one `Icon` set (replaces 4 `InfoIcon`s, text glyphs). Then `tokens.json` additions and regenerate.
2. **Callout** (70 copies, 18 without icon, wrong roles) with `retry` slot.
3. **Button** (112 uses; sizes, busy squares, disabled-with-reason) and **IconButton**, **Link**.
4. **StateTag + CountBadge + SampleLabel** (colour/word source of truth, DS-B-1..3, D-3, D-4, B-10).
5. **Segmented + Tabs** (8 + 7 copies; roving tabindex with Home/End), then **ShowMore**.
6. **SearchField + ListToolbar + FilterPanel (popover/sheet)** (7 + 4 copies) built on **Popover/BottomSheet**; then **Drawer** (merge alerts and start-work), **Dialog**, **Menu/SplitButton**.
7. **TextField/TextArea/Select/Checkbox/Radio/DateField/MoneyField + ValidationSummary + FileUpload** (28 inputs, 2 ProofFields).
8. **Panel + AgentChecklist + Avatar + DecisionPanel/PhoneActionBar** (7 agent-card copies, 3 decision panels).
9. **FactsStrip, StationTrack, MiniStationBar, WorkList, Table** (work-item/decide/my-work copies, month-end table).
10. **Disclosure, Breadcrumb, Loading/Empty/Error, Toast, Tooltip**, then (when built) ChatMessage, DraftCard, SourceTag.

Each step should migrate its callers in the same change and re-run the fidelity check on the screens marked "Look change: Yes".

## Limits of this audit

- Line-based greps can miss multi-line JSX; I re-checked inputs, buttons and callouts with a multi-line script. Counts of 18 icon-less callouts, 16 warning alerts, 4 silent problems and 27 `psl-btn--sm` are from scripts/greps and verified by reading a sample.
- I did not run the app, so contrast, wrap behaviour and fidelity were judged from CSS only.
- `app/frame-fixtures`, `app/*/page.tsx` stubs and test files were not audited in detail.
