# StationTrack

Shows every station of a work item's line in order, which are done, and where it is held.

| Station | Look | Means |
|---|---|---|
| Done | `ink` fill | earned |
| Current, needs a person | `signal` fill | someone must act here |
| Current, agent or service | `action-tint`, blue edge | processing |
| Waiting | `waiting-tint`, amber edge | waiting on someone else |
| Stopped | dashed `signal-ink` edge | held with a reason |
| Verified | `verified` fill | the output is verified |
| Not started | `rule-soft` edge, muted text | later |

- Each station has its number, name and a one-line status. 4 to 11 stations per line; scrolls sideways on phones, current station scrolled into view.
