# Decision 1 · Department assistants

PSL approved role-based access on 21 November 2026. The staff appointment determines what people and their assistants can read. Tola covers PMO, Chidi covers Finance, and Zainab covers HR. The factory checks access when a conversation opens, when the worker reads the sources and when someone reads a saved answer. Individual project approvals still govern the older account path.

| Check | Result |
| --- | --- |
| PMO head on Railway | Tola offered **All department projects**. She found one project, **PSL Role Testing**, and zero recorded milestone completions. The answer cited the project list and the department record counts. [Department selector](../test-evidence/department-roles-2026-11-21/railway-pmo-scope.jpg) · [Live answer](../test-evidence/department-roles-2026-11-21/railway-tola-answer.jpg) |
| Finance head with two sample projects | Chidi offered **Coastal rollout**, **Northern launch** and a department-wide view. In a separate invoice fixture, she found **NGN 42** on the saved invoice. Opening her citation showed the invoice amount, with payment and balance marked unknown. [Finance selector](../test-evidence/department-roles-2026-11-21/finance-scope.jpg) · [Invoice answer and citation](../test-evidence/department-roles-2026-11-21/chidi-invoice-answer.jpg) |
| Project team member | The member saw only **Coastal rollout** in Projects and in Tola’s selector. The server also rejected a saved source link from the other project. [Member selector](../test-evidence/department-roles-2026-11-21/project-member.jpg) |
| HR staff | Zainab opened and answered that the live HR system is disconnected. [HR answer](../test-evidence/department-roles-2026-11-21/hr-connection.jpg) |

All browser checks used the Codex in-app browser. The PMO check used the hosted Railway design-acceptance account. The Finance, project-member and HR checks used isolated local PostgreSQL workspaces. All three named assistants produced answers through OpenRouter. No sample financial transactions were added to the hosted workspace.

Railway confirmed the final web deployment `3759256d-0b9d-4a66-8da4-4afda2a49c3d` and worker deployment `b3620c60-c5a2-4bfd-a643-4c4ca65474b3`. The final PMO answer was read back in a fresh in-app browser tab. [Hosted conversation for its owner](https://psl-design-web-design-acceptance.up.railway.app/assistant/35fdf70d-21aa-4991-a810-a3cda64870f5/)

The project and record counts cover the whole selected scope. A chat shows up to 30 project names and four examples per record type. Naming a project narrows the search. A matching reference or record number brings older records into view. Department record lists have pages for browsing the full register.

All 39 PostgreSQL checks passed in the role, department assistant, project data use, payroll recipient and business-unit recipient suites. Four focused checks passed again after the final changes to record lookup and invoice citations. The checks cover operational and sample separation, assignment changes, saved conversations, source links, the single PMO appointment, the Admin replacement path and independent Finance and PMO approvals. The operational-project test uses isolated records and a simulated provider. The browser screenshots above identify the checks that used the real provider.
