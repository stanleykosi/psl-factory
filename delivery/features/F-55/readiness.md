DECISION: READY
RISK: low
SURFACES: ui
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: coordinator (the design engineer asked on 20 Nov: "i need mock data for hr as well down to the necessary details page and chat with assistant as well. also dont hr have lines to start as well?")

## Summary
- D-142 added an `hr` stand-in persona (Amaka Obi, role HR) with empty queues. The design engineer wants to walk the app as HR end to end: My work rows, work item detail and history, alerts, Assistant conversations with Zainab, and a line to start.
- Source facts: HR's part in the process list is supplying and confirming the staff and business-unit records payroll is matched against (F17 "Match payroll to HR staff and BU membership", F35 "HR-to-finance information interface"); the HR Lead decides payroll corrections (SCR-37). Payroll itself is a Finance line. The payroll screens (SCR-09/18/37/59) are held on PSL decisions (D-PAYROLL-VISIBILITY, payroll rules).
- Engineering proposal, not a source fact: a stand-in startable line for HR, "Send the staff list for payroll" (line_key `hr_staff_list`), so the start flow can be walked. Marked sample/stand-in everywhere; PSL confirms or replaces it.
- Mock data only, plus whatever generic UI is needed to show it. No contract change (line_key is a free string in v7). No payroll amounts are shown anywhere: payroll visibility is undecided, so Zainab and the pages treat salary values as restricted.

## Risk
Low. Mock fixtures and stand-in data. The risk is presenting invented HR policy as real; every HR row and line is flagged sample and the stand-in line says so.
