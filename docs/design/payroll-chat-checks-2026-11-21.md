# Zainab’s payroll totals

PSL chose to show both the total staff cost and the breakdown by business unit. The person must be a current named recipient and must have acknowledged that exact reviewed report. Zainab reads the published amounts inside PSL. Employee names, employee IDs and individual pay are outside this answer.

| In-app browser check | Result |
| --- | --- |
| Named recipient opens the report | The report offered **Acknowledge this report**. After acknowledgement, **Ask Zainab for the total and breakdown** appeared. [Before acknowledgement](../test-evidence/payroll-chat-2026-11-21/before-acknowledgement.jpg) · [After acknowledgement](../test-evidence/payroll-chat-2026-11-21/after-acknowledgement.jpg) |
| Recipient asks Zainab | For September 2026, Zainab showed a total of 410.00 in the sample currency, with 250.00 for BU-A and 160.00 for BU-B. Her citation opened the reviewed report with the same amounts. [Answer and citation](../test-evidence/payroll-chat-2026-11-21/zainab-totals.jpg) |
| Another member of the same Finance team | That person’s report list was empty. Opening the recipient’s saved report link showed the access message and no figures. [Report list](../test-evidence/payroll-chat-2026-11-21/other-member-empty.jpg) · [Saved link](../test-evidence/payroll-chat-2026-11-21/other-member-report-denied.jpg) |
| Railway design-acceptance | The signed-in account opened **Assistant → My acknowledged payroll reports**. Its list was empty. [Hosted page](https://psl-design-web-design-acceptance.up.railway.app/assistant/payroll/received/) · [Browser screenshot](../test-evidence/payroll-chat-2026-11-21/railway-reports.jpg) |

The positive walkthrough used an isolated PostgreSQL sample project, two Finance members admitted through staff invitations, and a normally published report covering four fictional employees. Each unit met that report’s configured minimum group size. No payroll records were added to Railway. The totals path makes no OpenRouter call.

Railway reported successful deployments for the [web application](https://railway.com/project/f957481b-c6f7-43af-bc66-449a330a9d53/service/ac6b2ef8-4bd1-4dcf-9c28-5ef5b0de0de3?id=215c6f8b-f11e-495b-af20-bd88869cd105) and [background worker](https://railway.com/project/f957481b-c6f7-43af-bc66-449a330a9d53/service/9959671c-482b-4384-9164-13b532b6dc83?id=32a6cf0f-9d63-4665-b25d-872ce27c807d). The hosted health check returned `ok`.

Seventy PostgreSQL tests passed across payroll calculation, report delivery and acknowledgement, Zainab’s answers, and staff access. Two further project-permission tests passed, including a check that allowing these totals inside PSL does not allow payroll information to be sent to an external AI service. Django found no missing database migrations.
