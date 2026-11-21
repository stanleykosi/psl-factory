"""Render the 122 existing process contracts for implementation and owner review."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def render():
    sys.path.insert(0, str(ROOT))
    from apps.workflows.factory_processes import PROCESS_IDS

    stations = {}
    for line, processes in PROCESS_IDS.items():
        for process in processes:
            stations.setdefault(process, []).append(line)
    rows = load("contracts/process-map.json")["rows"]
    assignments = load("reference/08-agent-architecture/process-agent-assignments.json")["assignments"]
    by_id = {item["id"]: item for item in assignments}
    execution_rows = load("reference/12-payment-exception-policy/process-execution-bindings.json")
    bindings = {item["id"]: item for item in execution_rows}
    ids = {row["id"] for row in rows}
    if (
        len(ids) != 122
        or any(len(records) != len(ids) for records in (rows, assignments, execution_rows))
        or ids != set(by_id)
        or ids != set(bindings)
    ):
        raise ValueError("The catalogue, specialist assignments and execution contracts must contain the same 122 processes exactly once.")
    if set(stations) - ids or any(by_id[process]["department"] == "BaaS" for process in stations):
        raise ValueError("A native release station refers to an unknown or deferred process.")
    specialists = {f"A{i:02}" for i in range(1, 9)}
    for row in rows:
        team = by_id[row["id"]]["specialist_roles"]
        members = [role["id"] for role in team]
        primary = [role for role in team if role["assignment"] == "Primary capability for this process"]
        if (
            not team
            or primary != team[:1]
            or len(members) != len(set(members))
            or set(members) - specialists
            or by_id[row["id"]]["department"] != row["department"]
            or any(not role["process_responsibility"].strip() for role in team)
        ):
            raise ValueError(f"Review the primary specialist, supporting tasks and department for {row['id']}.")
    lines = [
        "# Per-process specialist routing",
        "",
        "Defined work, approval boundaries and outputs. Runtime acceptance is recorded in BUILD-TESTS.md.",
        "O01 owns dispatch and resumption for connected factory work. Supporting roles run when the corresponding task is eligible.",
        "",
    ]
    for row in sorted(rows, key=lambda record: (record["workflow_family_id"], record["id"])):
        plan = by_id[row["id"]]
        lines.extend(
            [
                f"## {row['id']} · {row['title']}",
                "",
                f"{row['workflow_family_id']} · {row['source_owner']} · "
                + ("Deferred BaaS scope" if row["department"] == "BaaS" else "Release scope"),
                "",
                "**Direct Start work station** "
                + (", ".join(stations.get(row["id"], []))
                   or "No direct O01 station binding. This process retains its source contract and domain controls."),
                "",
                f"**Trigger** {row['trigger']}",
                "",
                "**Required input**",
                "",
            ]
        )
        lines.extend("- " + s for s in row["inputs"])
        lines.extend(["", "**Specialist tasks**", ""])
        for role in plan["specialist_roles"]:
            lines.append(f"- {role['id']} · {role['assignment']}. {role['process_responsibility']}")
        for title, items in [
            ("Domain checks", row["deterministic_responsibility"]),
            ("Permitted judgments", plan["permitted_autonomous_judgment"]),
            ("Internal tools and actions", plan["permitted_bounded_internal_actions"]),
            ("Entry checks", [plan["entry_gate"]["process_specific_gate"]]),
            (
                "Human decisions and open authority",
                row["human_responsibility"]["source_responsibilities"]
                + row["human_responsibility"]["prescribed_or_unresolved_authorities"],
            ),
            ("Downstream outputs", row["outputs"]),
            ("Limits on execution", plan["forbidden_actions"]),
            ("Owner questions", plan["unresolved_owner_dependencies"]["questions"]),
        ]:
            lines.extend(["", f"**{title}**", "", *["- " + x for x in items]])
        lines.extend(
            [
                "",
                "**Tool contracts** " + ", ".join(x["contract_id"] for x in row["agent_tool_contracts"]),
                "",
                "**Policy dependencies** "
                + (", ".join(row["policy_slot_ids"]) or "See the process execution binding."),
                "",
                "**Resume or escalate** " + plan["escalation_fallback"]["behavior"],
                "",
                *["- " + item for item in plan["escalation_fallback"]["process_exceptions"]],
                "",
                "**Execution contracts** " + ", ".join(bindings[row["id"]]["execution_contracts"]),
                "",
                "**Acceptance scenarios from the design**",
                "",
            ]
        )
        for example in plan["acceptance_evaluation_examples"]:
            lines.append(f"- {example['id']} · {example['scenario']} {example['expected']}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check source contracts and the saved routing book without writing files.")
    target = ROOT / "docs/design/specialist-process-routes.md"
    book = render()
    if parser.parse_args().check:
        if target.read_text(encoding="utf-8") != book:
            parser.exit(1, "The specialist routing book differs from the current process contracts.\n")
        print("All 122 process routes match their source contracts and the saved routing book.")
    else:
        target.write_text(book, encoding="utf-8", newline="\n")
