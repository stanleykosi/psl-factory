# Ordinary planning capture forms

The planning workbench now provides source selectors for Product PRD/requirements, scope and Engineering/Security estimates, four fixed stakeholder-team rows with current case participant/evidence selectors, and bounded question/disposition/action/evidence rows. All choices are filtered to the actual case and permitted public source kinds. Domain-private planning records and generated approval-subject wrappers are excluded from source selectors. Unknown sources/contacts stay blank rather than choosing a person or zero value.

**Add a question row without saving** performs a server-rendered preview that retains entered fields and creates no evidence, audit, assignment or policy record. The form caps questions at100 and stakeholder rows at the four source-prescribed teams, regardless of submitted management counts. No JavaScript or external provider is required.

**Record planning packet version** calls the same current domain service as the advanced typed protocol. It checks actor purpose, case, explicit latest predecessor, current contact participation and source/action references under existing locks. It creates an immutable successor; deleting a question from this successor preserves prior packet history. It grants no approval, contact permission or action ownership and calculates no deadline.

The advanced JSON interface and typed owner-criteria forms remain available. Formal meeting/action ownership/deadlines and department source decisions remain in their owning workbenches. Missing criteria or source authority holds dependent readiness rather than packet capture. Generic planning privacy boundaries remain in force.

Actual PostgreSQL tests use real authenticated Django clients, CSRF, services and database records for preview/no-write behavior, unknowns, current contacts, foreign/private source rejection, management bounds, stale predecessor, coordination revocation and omission/history. The broader regression and retained test-placement error are recorded in BUILD-TESTS.md. Actual people, owner policy values, native source authenticity and operational UAT remain later inputs.
