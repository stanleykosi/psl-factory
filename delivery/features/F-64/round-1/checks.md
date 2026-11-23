GATE: FAIL
COMMIT: 9ca94904a8c2dcf05636823f9010e1b6da6403fc
ATTEMPT: 1

## Summary
- checks.sh failed with exit 2
- Protected paths: none changed
- Commit 9ca94904a8c2, round 1, attempt 1

## checks.sh (last 80 lines of checks.log)

```
== backend: django system check
System check identified no issues (0 silenced).
== frontend: install, lint, typecheck, test, build

added 457 packages in 2m

> psl-factory-frontend@0.1.0 lint
> eslint . --max-warnings 0


> psl-factory-frontend@0.1.0 typecheck
> tsc --noEmit

tests/decide.test.tsx(45,3): error TS2739: Type '{ invoice_id: number; version: number; sha256: string; amount: string; currency: string; recipient: string; preparation_id: number; sources: never[]; }' is missing the following properties from type '{ invoice_id: number; version: number; sha256: string; amount: string; currency: string; recipient: string | null; preparation_id: number; basis: string; prepared_by: string; prepared_at: string; sources: { ...; }[]; }': basis, prepared_by, prepared_at
tests/decide.test.tsx(54,91): error TS2322: Type '{ id: number; case_id: string; title: string; line: string; state: "ready" | "waiting" | "action_needed" | "owner_needed" | "setup_needed" | "verified" | "cancelled" | "awaiting_reconciliation" | "followup_needed" | "processing" | "effect_uncertain"; ... 33 more ...; proofs_url?: string | ... 1 more ... | undefined; }' is not assignable to type '{ id: number; case_id: string; title: string; line: string; state: "verified" | "waiting" | "ready" | "action_needed" | "owner_needed" | "setup_needed" | "cancelled" | "awaiting_reconciliation" | "followup_needed" | "processing" | "effect_uncertain"; ... 33 more ...; proofs_url: string | null; }'.
  Types of property 'reference' are incompatible.
    Type 'string | null | undefined' is not assignable to type 'string | null'.
      Type 'undefined' is not assignable to type 'string | null'.
tests/decide.test.tsx(293,9): error TS2739: Type '{ at: string; station: string; status: string; task_id: number; actor: string; reason: string; evidence_id: number; }' is missing the following properties from type '{ at: string; station: string; status: string; task_id?: number | undefined; actor?: string | undefined; reason?: string | undefined; actor_kind: "worker" | "person"; entry_id: number; evidence_id?: number | ... 1 more ... | undefined; }': actor_kind, entry_id
tests/shell-live.test.tsx(95,28): error TS2345: Argument of type '{ name: string; work_desk_url: string; destinations: { key: string; title: string; django_url: string; }[]; startable_lines: string[]; csrf_token: string; assistant_agents: "tola"[]; }' is not assignable to parameter of type '{ name: string; work_desk_url: string; destinations: { key: string; title: string; django_url: string; url: string; available: boolean; }[]; startable_lines: string[]; csrf_token: string; assistant_agents: ("tola" | ... 1 more ... | "zainab")[]; positions: { ...; }[]; }'.
  Property 'positions' is missing in type '{ name: string; work_desk_url: string; destinations: { key: string; title: string; django_url: string; }[]; startable_lines: string[]; csrf_token: string; assistant_agents: "tola"[]; }' but required in type '{ name: string; work_desk_url: string; destinations: { key: string; title: string; django_url: string; url: string; available: boolean; }[]; startable_lines: string[]; csrf_token: string; assistant_agents: ("tola" | ... 1 more ... | "zainab")[]; positions: { ...; }[]; }'.
tests/shell-live.test.tsx(95,58): error TS2345: Argument of type '{ name: string; work_desk_url: string; destinations: { key: string; title: string; django_url: string; }[]; startable_lines: string[]; csrf_token: string; assistant_agents: "tola"[]; }' is not assignable to parameter of type '{ name: string; work_desk_url: string; destinations: { key: string; title: string; django_url: string; url: string; available: boolean; }[]; startable_lines: string[]; csrf_token: string; assistant_agents: ("tola" | ... 1 more ... | "zainab")[]; positions: { ...; }[]; }'.
  Property 'positions' is missing in type '{ name: string; work_desk_url: string; destinations: { key: string; title: string; django_url: string; }[]; startable_lines: string[]; csrf_token: string; assistant_agents: "tola"[]; }' but required in type '{ name: string; work_desk_url: string; destinations: { key: string; title: string; django_url: string; url: string; available: boolean; }[]; startable_lines: string[]; csrf_token: string; assistant_agents: ("tola" | ... 1 more ... | "zainab")[]; positions: { ...; }[]; }'.
tests/shell-live.test.tsx(95,88): error TS2345: Argument of type '{ name: string; work_desk_url: string; destinations: { key: string; title: string; django_url: string; }[]; startable_lines: string[]; csrf_token: string; assistant_agents: "tola"[]; }' is not assignable to parameter of type '{ name: string; work_desk_url: string; destinations: { key: string; title: string; django_url: string; url: string; available: boolean; }[]; startable_lines: string[]; csrf_token: string; assistant_agents: ("tola" | ... 1 more ... | "zainab")[]; positions: { ...; }[]; }'.
  Property 'positions' is missing in type '{ name: string; work_desk_url: string; destinations: { key: string; title: string; django_url: string; }[]; startable_lines: string[]; csrf_token: string; assistant_agents: "tola"[]; }' but required in type '{ name: string; work_desk_url: string; destinations: { key: string; title: string; django_url: string; url: string; available: boolean; }[]; startable_lines: string[]; csrf_token: string; assistant_agents: ("tola" | ... 1 more ... | "zainab")[]; positions: { ...; }[]; }'.
npm warn EBADENGINE Unsupported engine {
npm warn EBADENGINE   package: 'jsdom@31.0.1',
npm warn EBADENGINE   required: { node: '^22.22.2 || ^24.15.0 || >=26.0.0' },
npm warn EBADENGINE   current: { node: 'v24.12.0', npm: '11.6.2' }
npm warn EBADENGINE }
npm warn EBADENGINE Unsupported engine {
npm warn EBADENGINE   package: 'w3c-xmlserializer@6.0.0',
npm warn EBADENGINE   required: { node: '^22.22.2 || ^24.15.0 || >=26.0.0' },
npm warn EBADENGINE   current: { node: 'v24.12.0', npm: '11.6.2' }
npm warn EBADENGINE }
npm warn deprecated eslint@9.39.5: This version is no longer supported. Please see https://eslint.org/version-support for other options.
```
