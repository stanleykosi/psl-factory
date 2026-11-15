# Shared components

One React component per design-system component the app needs (D-91), built from
`design/system/project/components/<Name>/` (README.md and preview.html) and the classes in
`src/styles/psl-bundle.css`. Markup, class names and states follow the spec, so replacing a feature's
hand-written `psl-*` markup with the component should not change how it looks. `components.css` holds
only what the bundle does not draw (popover and overlay placement, screen-reader text, phone targets), as
`cmp-*` classes or `psl-*` classes narrowed by a `cmp-*` one, from tokens.

Import from `@/components`. Tests are in `frontend/tests/components/` (render, states, keyboard, axe).

| Component | Spec folder | CMP | Test file |
|---|---|---|---|
| `Icon`, `ICON_NAMES` | Icon | (icons) | icon.test.tsx |
| `Button`, `buttonClass`, `BusySquares` | Button | | button.test.tsx |
| `IconButton` | IconButton | | button.test.tsx |
| `Link`, `RestrictedLink` | Link | | link.test.tsx |
| `Callout` | Callout | CMP-24 | callout.test.tsx |
| `Tag`, `StateTag`, `STATE_TAGS`, `PriorityTag` | StateTag | CMP-05 | tag.test.tsx |
| `CountBadge` | CountBadge | CMP-06 (counts) | count-badge.test.tsx |
| `SampleLabel` | SampleLabel | CMP-16 | sample-label.test.tsx |
| `Panel` | Panel | | panel.test.tsx |
| `TextField` | TextField | | text-field.test.tsx |
| `TextArea` | TextArea | | text-field.test.tsx |
| `Select` | Select | | select.test.tsx |
| `DateField`, `parseDate` | DateField | | date-field.test.tsx |
| `MoneyField` | MoneyField | | money-field.test.tsx |
| `Checkbox` | Checkbox | | checkbox-radio.test.tsx |
| `RadioGroup` (radios and choice cards) | Radio | | checkbox-radio.test.tsx |
| `Segmented` | Segmented | CMP-06 rule | segmented-tabs.test.tsx |
| `Tabs` | Tabs | CMP-06 | segmented-tabs.test.tsx |
| `Menu`, `MenuButton`, `useMenuButton` | Menu | | menu.test.tsx |
| `SplitButton` | SplitButton | CMP-23 | menu.test.tsx |
| `SearchField` | SearchField | CMP-22 | search-toolbar.test.tsx |
| `ListToolbar`, `FilterPanel` | ListToolbar | CMP-22 | search-toolbar.test.tsx |
| `FileUpload` | FileUpload | CMP-20 (proof) | file-upload.test.tsx |
| `Drawer` | Drawer | CMP-23 (drawer) | overlays.test.tsx |
| `BottomSheet` | BottomSheet | | overlays.test.tsx |
| `Dialog` | Dialog | | overlays.test.tsx |
| `Toast` | Toast | | toast-tooltip.test.tsx |
| `Tooltip` | Tooltip | | toast-tooltip.test.tsx |
| `Table` | Table | | table.test.tsx |
| `ShowMore` | ShowMore | CMP-07 (50 rows) | lists-and-states.test.tsx |
| `Loading`, `Skeleton`, `EmptyState`, `ErrorState`, `Progress` | Loading | CMP-07 states | lists-and-states.test.tsx |
| `Breadcrumb` | Breadcrumb | | lists-and-states.test.tsx |
| `Disclosure` | Disclosure | | lists-and-states.test.tsx |
| `ValidationSummary` | ValidationSummary | | lists-and-states.test.tsx |
| `AgentAvatar`, `PersonAvatar`, `AgentChip` | Avatar | CMP-18 | domain.test.tsx |
| `FactsStrip` | FactsStrip | CMP-04 | domain.test.tsx |
| `StationTrack` | StationTrack | CMP-02 | domain.test.tsx |
| `MiniStationBar` | MiniStationBar | CMP-03 | domain.test.tsx |
| `AgentChecklist` | AgentChecklist | CMP-09 | domain.test.tsx |
| `PhoneActionBar` | PhoneActionBar | CMP-11 | domain.test.tsx |

Foundations (the audit's step 1), not design-system components of their own:

| Export | What | Test file |
|---|---|---|
| `formatDate`, `formatTime`, `formatDateTime`, `formatAmount`, `groupDigits`, `UNKNOWN` (`format.ts`) | "17 Nov 2026", "14:30 WAT", "₦4,250,000.00"; missing is "Unknown", never 0 | date-field, money-field |
| `Money`, `When`, `Unknown` (`Values.tsx`) | the same in mono, with the amber Unknown tag | money-field, lists-and-states |
| `PageTitle` | the `page-title` text style | lists-and-states.test.tsx |
| `VisuallyHidden` (`cmp-sr`) | screen-reader-only text | lists-and-states.test.tsx |
| `useIsPhone` | below `bp-phone` (720px) | overlays.test.tsx (Drawer as sheet) |

Not built yet, because no feature implements them (D-91: domain components only where a feature already
has one): DecisionPanel (the decide feature's panel is its own; PhoneActionBar is built), WorkList (My work
draws a table), SourceTag, DraftCard, ChatMessage (the assistant page is a stub), TopNav and AlertMessage
(the shell and the alerts feature own them).

Rules the components hold for every caller:

- Tags use the five families only and always carry words; state words come only from `STATE_TAGS`.
- Unknown is written "Unknown" (the amber tag); `MoneyField` keeps `null` for Unknown and `''` for empty.
- Agents never get Approve, Send or Pay: `AgentChecklist` has no decision buttons.
- Busy buttons keep their width, show the three squares and ignore presses; disabled ones carry a reason.
- Modal surfaces trap focus, close on Esc and return focus; menus and lists return focus to their control.
- Reduced motion is the bundle's: pulses, spinners and busy squares stop.
