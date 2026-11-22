# Eight specialists through human approval and receipt

On 22 November 2026, three synthetic cases on Railway exercised all eight specialist roles with the real OpenRouter model `deepseek/deepseek-v4.1-flash-1017`, PostgreSQL and private object storage. Each specialist cited source lines and wrote a private report. The test read back every file and checked its full digest.

**All nine readings returned `insufficient`.** The assigned information reviewer acknowledged the open questions. A different, authorised test principal then approved the exact Finance source, document version or HR disclosure through its business service. The coordinator verified the downstream record. The tests executed those human-role services programmatically. They demonstrate escalation and receipt verification on these limited inputs. They do not establish that the specialists resolved these cases independently.

| Process and evidence supplied | Information reviewer | Independent decision | Downstream record |
| --- | --- | --- | --- |
| F02 · Trial-balance import inventory, validation status, declared control total and source fingerprint | Finance preparer 130 | Finance reviewer 132 approved source review 6 | Finance mapping run 1 pins source review 6 |
| F35 · Requested reporting period, request revision and read-only disclosure conditions | Finance recipient 134 | HR owner 133 approved disclosure record 4 | Recipient 134 acknowledged the exact authorised snapshot in Finance receipt 5 |
| P52 · Document type, audience, template/document revisions, source count and content fingerprint | Document preparer 135 | PMO reviewer 137 approved document review 1 | The reviewed version reached its named recipient with publication receipt 1 |

Each row below identifies the exact bytes retrieved from private storage. The filenames, source contents and model responses stay outside this ledger.

| Process | Specialist | Cited lines | Private report SHA-256 |
| --- | --- | --- | --- |
| F02 | A01 · Intake and case triage | 5, 4, 3 | `64b25c72bcb9fc686698361f00c85cf284e71bc284b7d5ebd96aad05f747786b` |
| F02 | A03 · Exception investigation | 1, 4, 5 | `56db967e8ec8631f4f3cbd4bb46c3244a86364279d072606dd40f2f83ac39d89` |
| F02 | A05 · Finance evidence and analysis | 1, 4 | `dd7075c35bdfcb1a8be45a60d0c6be0832498733d075c54250d8a9667871c87c` |
| F35 | A02 · Evidence and document analysis | 1, 2 | `f122e2d28ac6c50a93a937dcff8ce031d56ceb8fdd5fa80ee66f583aa9a0f935` |
| F35 | A04 · Planning and workflow coordination | 1, 2 | `ae672ffaaff2dc5c01ab881fd51c003c0c44a81c879418326b097062f6e1d2ad` |
| F35 | A07 · Control evidence and release preflight | 1, 2 | `c506b5b6b45fcfe66f3a85662c4eb6f29ebd92c49bd415b314fbaeefe7c52b69` |
| P52 | A02 · Evidence and document analysis | 1, 2, 3, 4 | `3879b01d802a750cb353432646cc41b65217cd87fe3af245d6aa552839f8bf67` |
| P52 | A06 · Management insight and drafting | 1, 2, 3, 4 | `91ab0d7dc6d13583d396f3dfc6ce5f30e6c25ff567bcb37800a51c61ae5e15fc` |
| P52 | A08 · Evaluation and quality review | 1, 2, 3, 4 | `359d92f5a221c7d7ccb45a9f0bed6dc28cc0bcb04f65c3891ec5cf7e32a8b3b7` |

The first image stopped during Django imports before it invoked the model. The corrected image passed the HR and PMO cases. Finance stopped because a fact proposed by A05 failed exact source-citation validation. The prompt was clarified to require string values copied exactly from a cited line. Validation stayed in place. A new synthetic F02 case alone was then run and passed in 40.193 seconds. The HR and PMO results came from the first paid run, which finished in 51.311 seconds with two passing cases and one failure. [Initial import check](https://railway.com/project/f957481b-c6f7-43af-bc66-449a330a9d53/service/00c14ca1-5361-4bee-97a5-2ec7aba6ef18?id=3a5c8cbe-5d76-4fff-8a95-efec6f0a78d0) · [HR and PMO receipts and Finance hold](https://railway.com/project/f957481b-c6f7-43af-bc66-449a330a9d53/service/00c14ca1-5361-4bee-97a5-2ec7aba6ef18?id=2c3c9d44-4b34-4901-8ce9-a1bb45e23468) · [Finance rerun and receipt](https://railway.com/project/f957481b-c6f7-43af-bc66-449a330a9d53/service/00c14ca1-5361-4bee-97a5-2ec7aba6ef18?id=c3484d0b-2f9d-440b-948c-90df6d84c048)

Each run used a fresh test database and a one-use ticket. The test recorded the storage versions created by native writes, removed those versions and verified their removal. The runner saved the machine-readable receipts in the acceptance audit database and removed each test clone. Both temporary OpenRouter references were removed from the Railway checks service and their absence was verified. No external customer, banking, HR or accounting destination was used.
