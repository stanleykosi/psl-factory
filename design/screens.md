# Screen inventory

Every screen the approved journeys need, with its states and its artboards on the
canvas. One line per screen; IDs stay stable for the life of the project, and
delivery tasks reference them. Replace every <placeholder>.

Format: `- SCR-n | J-n[, J-n] | Screen title | states: default, empty, loading, error | components: CMP-n, CMP-n | artboards: SCR-n-desktop, SCR-n-mobile`

## Screens

- SCR-01 | J-01 | <screen title> | states: default, empty, error | components: CMP-01 | artboards: SCR-01-desktop, SCR-01-mobile

## Data each screen shows

- SCR-01 — <records and endpoints from the architecture package, e.g. GET /bookings>

## Revisions

- <date> — <what changed and why> — canvas version <id>
