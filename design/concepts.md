# Design concepts

Each concept is a distinct direction applied to the same key screens with the same
real content, so the client compares directions, not content. One line per concept
records its decision: proposed, chosen, merged or rejected.

Key screens in every concept, in this order: Work queue (desktop, the screen people
see most), Work item (desktop, carries the core journey J-01/J-04), Decision (phone,
J-02). Content is the same sample set in all three and is labelled as sample data
(R-06): six work items across invoice, commercial, go-live, planning, payroll and
closure lines, and one invoice decision.

Named sections, identical in every concept so sections can be mixed:
- Work queue: SEC-nav, SEC-floor, SEC-queues, SEC-list
- Work item: SEC-header, SEC-facts, SEC-stations, SEC-agent, SEC-decision
- Decision (phone): SEC-ask, SEC-detail, SEC-actions

## Decisions

- CON-A | rejected | Control room - people who handle a lot of work want a dense, dark, keyboard-fast console where every state is readable at a glance | refs: REF-01, REF-02, REF-04, REF-05, REF-06
- CON-B | rejected | Studio ledger - PSL is a design studio, so its factory should read like a calm, well-set document that anyone can pick up without training | refs: REF-03, REF-07, REF-08, REF-12
- CON-C | chosen | Assembly line - the stations are the product, so every screen is organised around the line a piece of work travels and the facts it has earned | refs: REF-04, REF-06, REF-09, REF-11
- CON-D | rejected | Linear-style - work feels like a fast, quiet issue tracker: lists grouped by state, a progress glyph per item, properties at the side and a command bar | refs: REF-01, REF-02, REF-03

## CON-A Control room

- Thesis: PMO and Finance staff live in the factory all day; a dense dark console with a live schematic of the floor lets them scan many items, see state instantly and act without hunting.
- Type: Geist for everything, Geist Mono for IDs, times and amounts; 13px body, 12px table, 20/28px headings; tight leading.
- Colour: Ground #0E1113, Panel #161A1E, Line #2A3136, Text #E7EBED, Muted #9BA6AC, Signal amber #F0A43A (waiting and attention), Clear green #43C59E (verified), Flag coral #FF8466 (stops and uncertain).
- Layout and density: left navigation rail, 36px rows, 8px grid, 6px radius; about 14 work items visible on a laptop screen.
- Components: flat panels separated by 1px lines, small status chips with a dot and the state word, keyboard hints on primary actions.
- Imagery and icons: no imagery; the floor is a live line-and-node schematic; 1.5px stroke icons.
- Fits best when: speed and volume matter most; feels technical and heavy for occasional users and the CEO, and dark screens are harder in bright offices.
- Built from: REF-01 activity trail and item stepping; REF-02 compact cards with counts; REF-04 lanes and the "it recovers" story; REF-05 status-dot table; REF-06 nodes and joins for the floor.
- Canvas page: con-a

## CON-B Studio ledger

- Thesis: most users are not operators; a light, spacious, editorial layout that reads like a well-made project document builds trust and makes each fact easy to find.
- Type: Newsreader (serif) for headings and key figures, Instrument Sans for interface text; 15px body, 34/44px headings, generous leading.
- Colour: Paper #FFFFFF, Mist #F2F3F5, Ink #1A1D23, Slate #5A6270, Ultramarine #2F45C9 (actions), Moss #23704F (verified), Ochre #9A5B00 (waiting and stops).
- Layout and density: top navigation, content-led single column with a right margin for decisions, 56px rows, 14px radius; about 7 work items visible on a laptop screen.
- Components: soft cards with hairline borders, pill tabs, sentence-style status ("Waiting for Finance Lead since 10:40"), large calm buttons.
- Imagery and icons: an isometric line-drawn factory floor illustration that marks live counts at each station; rounded 1.75px icons.
- Fits best when: clarity and first impressions matter, including for leadership; shows fewer items at once, so heavy daily users scroll more.
- Built from: REF-03 isometric line drawing for the floor; REF-07 illustrated mood and the view switch; REF-08 split invoice counts and right-aligned amounts; REF-12 calm light shell and "what needs me today" home.
- Canvas page: con-b

## CON-C Assembly line

- Thesis: the factory's own model is the clearest interface; every screen leads with the line a piece of work travels and the separate facts it has earned, so nobody mistakes a draft for an approval.
- Type: Archivo (expanded weights) for headings and station names, IBM Plex Sans for text, IBM Plex Mono for IDs and amounts; 14px body, 28/40px headings.
- Colour: Steel #EEF0ED (ground), White #FFFFFF (surfaces), Graphite #1F2427 (ink and rules), Signal orange #D8461F (PSL accent and current station), Blue #2459D6 (actions), Green #22764A (verified), Amber #8A5A00 (waiting).
- Layout and density: a station track across the top of each work view, a facts strip under it, then content; 44px rows, 2px radius, 2px graphite rules; about 10 work items visible on a laptop screen.
- Components: station blocks with numbered steps, a six-fact strip (drafted, reviewed, approved, sent, receipt recorded, verified) with paid kept apart, agent steps in their own tinted column, square buttons.
- Imagery and icons: no imagery; the floor is an animated assembly track where work items move as tokens between stations; square-capped 2px icons.
- Fits best when: users need to understand where work is and why it is held; the strong structure and orange accent are bold, and the track takes vertical space on small phones.
- Built from: REF-04 station lanes and recovery story; REF-06 nodes and joins; REF-09 agent filling fields visibly beside the item; REF-11 agent step ticks and progress.
- Canvas page: con-c

## CON-D Linear-style

- Thesis: PSL's people already know modern issue trackers; borrowing Linear's interaction patterns (grouped lists, progress glyphs, properties panel, activity feed, command bar) makes the factory feel familiar and fast, with PSL's own colour and content.
- Type: Inter for everything at 13px, medium weight for titles, tabular numbers; one 22px title per screen.
- Colour: Charcoal #101114 (ground), Panel #16171B, Line #26282E, Text #E3E4E8, Muted #8C919B, PSL orange #E8693E (accent and "needs you"), Green #4CB782 (verified), Amber #D9A23C (waiting), Coral #EB6E6E (stops). Not Linear's indigo.
- Layout and density: sidebar with Inbox and lines listed like teams, grouped list with 40px rows, right properties panel on items, 6px radius.
- Components: station-progress circle (fills as stations complete), state group headers with counts, property rows, activity feed entries that name the actor type, a bottom action bar on phone.
- Imagery and icons: none; thin 1.5px icons and the progress circle as the signature.
- Fits best when: users are comfortable with modern work tools and want speed; close to concept A in feel, and it leans on another product's conventions rather than a PSL identity.
- Built from: REF-01 issue detail, activity and item stepping; REF-02 grouped cards with counts; REF-03 line-drawing restraint.
- Canvas page: con-d

Recommendation: CON-C, because it makes the factory's rules visible (R-01, R-03) for every role, with CON-B's light readability as the fallback if PSL finds C too bold. The client decides.

## Section map

Only when concepts are mixed: which concept each section comes from.

## Client feedback

- 2026-11-12 — design engineer (hunchoweb) — chose CON-C Assembly line overall; A and B not taken forward. Asked for an AI assistant, as a page or a drawer, which needs a scope change first. PSL confirms the direction when it approves the design.
- 2026-11-12 — design engineer — asked to also see a Linear-style concept; CON-D added for comparison, CON-C stays chosen until decided.
- 2026-11-12 — design engineer — stays with CON-C; D not taken forward. The assistant becomes its own page in C's style (scope v2: S-10, J-10, J-11, R-08).
- 2026-11-12 — design engineer — mascots named: Tola (PMO agent), Chidi (Finance agent), Zainab (HR agent). PSL to confirm no staff share these names.
