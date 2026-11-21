# F-55 HR stand-in sample data: work, detail, assistant and a line to start

Task: FE-HR-MOCK-DATA (coordinator-defined at the design engineer's request, 20 Nov). Mock data for the `hr` persona (D-142). No contract change; existing generic screens draw it. Everything here is sample data for viewing (`sample: true` where the shape allows) and a stand-in until PSL defines HR's role (D-PAYROLL-VISIBILITY open).

## Rules
- Follow the existing fixture shapes and the contract (frontend/mock, architecture/packages/v7/openapi.json). mock-contract tests must pass for every new fixture.
- Never show a salary or payroll amount. Where the shape carries an amount, it is `unknown` or the row is Restricted, matching INV-RESTRICTED.
- HR's work is about staff and business-unit records feeding payroll (F17, F35), never approving payroll or payments.
- Plain business wording; Nigerian sample names and companies in the style of the existing fixtures.

## Acceptance criteria
1. My work for `hr` shows sample rows in all three queues: Needs me (at least 3, e.g. confirm November staff list for payroll matching, resolve 2 staff with no business unit, answer Finance's question on a leaver), Waiting on others (at least 3, e.g. Finance matching the staff list, HR Lead deciding a payroll correction), Done (at least 2). Counts, filters and search work. — verify: e2e as hr.
2. Each HR row opens a work item page (/work/[id]) with header, facts, station track, agent card and the next step, plus a History tab with at least 5 entries (person, agent, evidence, one Restricted entry). — verify: e2e opens two HR items and their history.
3. Alerts: the bell and Notifications show at least 3 HR alerts linking to those items. — verify: e2e.
4. Assistant: the hr conversation list has at least 4 conversations with Zainab, each opening a full thread (person message, agent steps, answer, sources, and a draft or result card where it fits). One conversation asks for a salary and Zainab declines to show amounts, explaining payroll visibility is not set up yet and who can see it. Sending a new message to Zainab as hr returns a sensible mock reply. — verify: e2e opens two conversations and sends one message.
5. Start work: `hr` can start the stand-in line "Send the staff list for payroll" (line_key `hr_staff_list`), marked as a stand-in in its description, through the existing start flow (choose month, attach the staff list file, start), landing on a new work item. The startable list in me.hr.json includes it. — verify: e2e start as hr.
6. hr still cannot open Projects, Exceptions or Setup (refused as today). Other personas' data is unchanged. — verify: existing e2e plus one hr refusal check.
7. checks.sh and the full e2e pass.

## Out of scope
Payroll screens (SCR-09/18/37/59), an HR Lead persona, real HR policy, any contract change.
