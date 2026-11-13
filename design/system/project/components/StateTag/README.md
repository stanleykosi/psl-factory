# StateTag

Names a work item's state in the factory's own words. The colour family says who it waits on; the words say exactly why.

| Family | Means | Examples |
|---|---|---|
| orange (`signal-tint` / `signal-ink`) | a person must act | Action needed, Owner needed, Effect uncertain |
| amber (`waiting-tint` / `waiting-ink`) | waiting on someone else | Waiting on client, Awaiting reconciliation |
| blue (`action-tint` / `action-ink`) | agent or processing work only | Processing, Tola drafting, WORKING |
| green (`verified-tint` / `verified-ink`) | done or verified | Verified, Received |
| grey (`neutral-tint` / `neutral-ink`) | closed, not applicable, information | Cancelled, Out of scope, role labels |

- Always one line; the column grows to fit the longest state.
- Priority is a grey tag with a mono marker (■■■ high, ■■□ medium, ■□□ low), never a status colour.
- Never invent a synonym ("Done", "Complete") for a factory state.
