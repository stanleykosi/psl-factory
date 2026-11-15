# StateTag

Names a work item's state in the factory's own words. The colour family says who it waits on; the words say exactly why.

| Family | Means | Examples |
|---|---|---|
| orange (`signal-tint` / `signal-ink`) | a person must act | Ready to continue, Action needed, Owner needed, Setup needed |
| amber (`waiting-tint` / `waiting-ink`) | waiting on someone else (the client, an approver, a team), and an effect not yet confirmed | Waiting on client, Waiting on HR, Effect uncertain (D-92b), Awaiting reconciliation |
| blue (`action-tint` / `action-ink`) | agent or processing work only | Processing, Tola drafting, WORKING |
| green (`verified-tint` / `verified-ink`) | verified outputs only | Verified |
| grey (`neutral-tint` / `neutral-ink`) | closed, not applicable, information | Cancelled, Out of scope, role labels |

- Always one line, in capitals as the boards draw them (the words keep their case for screen readers); the column grows to fit the longest state.
- Priority is a grey tag with a mono marker (■■■ high, ■■□ medium, ■□□ low), never a status colour.
- Never invent a synonym ("Done", "Complete") for a factory state.
