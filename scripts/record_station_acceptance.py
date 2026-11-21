"""Write the per-process receipt ledger only from completed Railway suite output."""
import argparse
import os
from pathlib import Path
import re
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deployment", type=UUID)
    parser.add_argument("logs", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    import django
    django.setup()
    from apps.workflows.native_station_contracts import registry
    from apps.agents.specialists import routes

    text = args.logs.read_text(encoding="utf-8-sig")
    for suite in ("pmo", "accounts", "operations"):
        if not re.search(rf"^\[{suite}\] Passed receiver checks .* Missing \[\]\.", text, re.M):
            parser.error(f"A completed receipt suite is missing for {suite}.")
        if not re.search(rf"^\[{suite}\] OK\s*$", text, re.M):
            parser.error(f"The {suite} Django suite did not pass.")
    evidence = {}
    for pid, model in re.findall(r"\[(?:pmo|accounts|operations)\].*?Native station verified ([PF][0-9]{2}) -> ([a-z]+\.[a-z_0-9]+)", text):
        evidence.setdefault(pid, set()).add(model)
    if set(evidence) != set(registry()):
        parser.error("The completed receiver set differs from the release registry.")
    lines = ["# Department handoff acceptance on Railway", "",
             f"Checks deployment `{args.deployment}` verified each process below on isolated PostgreSQL with synthetic records. "
             "The grouped checks simulated model replies and file storage. The department services, specialist queues, permission checks, native approvals and receipt records ran in the application.",
             "", "Each internal receiving command checks the exact specialist handoff. P05 records the recipient's explicit acknowledgment. "
             "For P19 the customer response can arrive independently and PMO consumes the findings during signed-baseline adoption.",
             "", "| Process | Triggering record | Specialist team | Verified receiving record |", "| --- | --- | --- | --- |"]
    for pid in sorted(evidence, key=lambda key: (not key.startswith("P"), key)):
        route = registry()[pid]
        spec = routes()[pid]
        team = ", ".join(f"{r['id']} {r['name']}" for r in spec["specialist_roles"])
        receive = ", ".join(sorted(evidence[pid]))
        lines.append(f"| {pid} · {spec['original_title']} | {route.model} | {team} | {receive} |")
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
