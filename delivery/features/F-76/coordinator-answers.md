# F-76 readiness answers

- D-182 (23 Nov 2026, design engineer, batch question B13): "Read-only list now". The staff list and person page ship read-only (GET /staff, GET /staff/{id}); invite, deactivate, restore and role changes wait for PSL's D-ADMIN-AUTHORITY and are not drawn as active controls.
- D-182 general rule: "Hide, accept all recs" — where the live API does not supply something a board draws (the people count, "Last signed in", invite and deactivation dates, role-per-workspace wording), hide that part and switch it on when the backend adds the data. This is the recorded exception you asked for.
- A-53 (who may open the screen): build on the server's answer — show the list to whoever the server serves it to, and the existing forbidden state on 403; flag it in the spec and PR.
- Scope: this is the F-76a slice you proposed; it keeps the id F-76 and task FE-SETUP-ROLES. Under D-180 the task's D-ADMIN-AUTHORITY gate holds only the writes, which are out of scope.
- Standing answers otherwise as in delivery/features/F-73/coordinator-answers.md.
