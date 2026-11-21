"""Render the 122 existing process contracts for implementation and owner review."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def render():
    sys.path.insert(0, str(ROOT))
    from apps.workflows.factory_processes import PROCESS_IDS

    stations = {process: line for line, ids in PROCESS_IDS.items() for process in ids}
    rows = load("contracts/process-map.json")["rows"]
    assignments = load("reference/08-agent-architecture/process-agent-assignments.json")["assignments"]
    by_id = {item["id"]: item for item in assignments}
    bindings = {
        item["id"]: item
        for item in load("reference/12-payment-exception-policy/process-execution-bindings.json")
    }
    if len(rows) != 122 or set(by_id) != {row["id"] for row in rows}:
        raise ValueError("Process assignments and source contracts differ")
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
                + stations.get(
                    row["id"],
                    "No direct O01 station binding. This process retains its source contract and domain controls.",
                ),
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
    (ROOT / "docs/design/specialist-process-routes.md").write_text(render(), encoding="utf-8", newline="\n")
