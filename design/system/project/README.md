# PSL Factory

The design system for PSL's operations factory, from concept C, Assembly line. Every screen is organised around the line a piece of work travels and the separate facts it has earned, so nobody mistakes a draft for an approval.

## Content fundamentals

- Write in plain business language. Name records the way PSL staff do: invoice, SOW, plan, milestone, go-live report. Keep technical references (INV-0412) secondary, in `mono`.
- Use the factory's own state words exactly: Ready to continue, Processing, Waiting, Awaiting Finance decision, Owner needed, Setup needed, Action needed, Effect uncertain, Awaiting reconciliation, Verified, Cancellation requested, Cancelled. Never invent synonyms such as "Done" or "Complete" for a state.
- Facts are never merged. Drafted, reviewed, approved, sent, receipt recorded and verified each get their own word and their own box; paid is a Finance fact and always sits apart.
- Say what an action does not do: "Approving does not send the invoice."
- Unknown is written "Unknown", never 0, never blank.
- Agents prepare and explain; they never "decide", "approve" or "send". Write "The Finance evidence agent drafted v2", not "The system approved".
- Sample, test and mock content always carries a label: SAMPLE DATA, TEST TEMPLATE, MOCK DELIVERY.

## Visual foundations

- **The line is the structure.** Panels and tables sit on `steel` in `surface` boxes bounded by a `rule-strong` (2px) border in `ink`. Corners are `radius-none`; buttons and tags take `radius-sm`.
- **Colour has one job each.**
  - `signal` (PSL orange) means "a person must act here": the current station, the decision panel's header, Start work and the navigation underline.
  - `action` (blue) is for buttons and links, and for everything agents do: agent panels use `action-tint` with an `action` border.
  - `verified` (green) is for verified outputs.
  - `waiting` (amber) is for waiting and for sample labels.
  - Every state is also written in words, so colour is never the only signal.
- **Facts strip:** earned facts are `ink` with `on-strong` text; the current one is `signal-tint` with `signal-ink` text; facts not yet earned are `surface` with `ink-muted` text.
- **Type:**
  - `display` (Archivo, expanded) is for screen titles and station names.
  - `sans` (IBM Plex Sans) is for all reading text.
  - `mono` (IBM Plex Mono) is for references, times, amounts and uppercase labels at 0.06em tracking.
- **Spacing:** a 4px base. Panels use `space-4`, sections `space-5`, desktop page gutters `space-6`. Every touch target is at least `space-7` (44px).
- **Contrast:** the signal orange is #C8401C, deepened from concept C's #D8461F, which was 4.4:1 with white text. Every text pair in this system meets 4.5:1.

## Motion

- Motion explains a change of state; it never decorates.
- **Station changes:** a work item's token slides to the next station and the fact it earned fills in, over 240–320ms with an ease-out curve (GSAP in the build).
- **Factory floor:** in the 3D/WebGL overview (three.js), work moves along each line as tokens between square stations.
- **Reduced motion:** for people who have turned motion down, the floor shows counts without movement, and state changes cross-fade in 120ms.
- Dense working screens (queue, decisions, Finance tables) do not animate content while people read.

## Iconography

- Stroke icons, 2px with square caps, drawn on a 20px grid in `ink`.
- Stations are squares and agents are marked with a square badge; people get round avatars.
- No emoji, no illustrations inside working screens.

## Using it

- Load the three Google Fonts families (Archivo with width axis, IBM Plex Sans, IBM Plex Mono).
- Build screens from these tokens only.
- The Next.js frontend in `frontend/` reads `tokens.json` to generate its CSS variables.
