# F-53 Design-system conformance, part 2: shared components everywhere

Task: FE-DS-CONFORMANCE-2 (coordinator-defined, at the design engineer's request). No endpoint, contract or data change. Screens: every merged screen that contains one of the 34 raw elements (the list is in readiness.md; find them with `grep -rnE "<(button|input|select|textarea|table)[ >]" --include="*.tsx" src/features src/app`). The design check passes under EXCEPTION D-89.

## Rules
Use only the shared components from `@/components`. Where a component lacks an option a screen needs (e.g. Button as a link-style button, a native datetime in DateField, a remove chip, an agent chip), extend the shared component additively, so existing uses don't change. Don't change wording, data, layout intent or behaviour beyond what the component brings: its focus handling, 44px targets on phones, busy and disabled states, and labels.

## Acceptance criteria
1. No raw `<button>`, `<input>`, `<select>`, `<textarea>` or `<table>` remains in `src/features` or `src/app`. All 34 are replaced with shared components, or with a shared component extended for the need. — verify: the grep above returns nothing.
2. An ESLint rule fails on any raw `<button>`, `<input>`, `<select>`, `<textarea>` or `<table>` JSX in `src/features` and `src/app` (allowed in `src/components`). A deliberate violation fails lint. — verify: lint run on a scratch violation, then removed.
3. Each extended shared component keeps its existing uses unchanged: its existing tests pass, and new options have tests.
4. Every replaced control keeps its accessible name, its keyboard behaviour (Enter or Space, focus order) and its disabled or busy state. On phones, every replaced control target is at least 44 by 44 px. — verify: component tests, plus e2e measurements on the response form, the RFP follow-up and My work at 390.
5. The visible result on the affected screens matches the merged look. The WorkItemOverview table now uses the shared Table styling. The ResponseForm radio, checkbox, select and datetime now use the shared RadioGroup, Checkbox, Select and DateField. — verify: before and after screenshots at 1440 and 390 of the response form, RFP outcome and follow-up, My work filters, Setup templates and the work item overview, attached to build.md.
6. All existing unit tests and e2e pass. Update tests only where they queried raw elements; never weaken an assertion. — verify: checks.sh plus the e2e for response, rfp, my-work, setup, projects, payments, work-item and assistant.

## Out of scope
New visual design. Any change to data, contract or authority.
