"""One-shot authoring helper: add input_schema to every CONDITION
node across all modules that needs user input. Idempotent — skips
nodes that already have input_schema."""

from __future__ import annotations

import json
from pathlib import Path

EDITS = {
    "benefits_enrollment_navigator": {
        "medicare_check": [
            {"key": "medicare_eligible",
             "label": "Is the patient Medicare-eligible?",
             "type": "boolean", "required": True,
             "description": "Yes if the patient is 65+, has been on SSDI for 24+ months, or has ESRD/ALS."},
        ],
        "medicaid_branch": [
            {"key": "medicaid_eligible_count",
             "label": "How many people in the household qualify for Medicaid?",
             "type": "number", "required": True,
             "description": "Enter 0 if no one qualifies."},
        ],
        "chip_branch": [
            {"key": "chip_eligible_count",
             "label": "How many children in the household qualify for CHIP?",
             "type": "number", "required": True,
             "description": "Enter 0 if no children qualify."},
        ],
        "aca_branch": [
            {"key": "aca_eligible_count",
             "label": "How many people qualify for an ACA marketplace plan?",
             "type": "number", "required": True,
             "description": "Enter 0 if no one qualifies."},
        ],
        "sep_check": [
            {"key": "enrollment_window_open",
             "label": "Is open enrollment currently open, or does the patient qualify for a Special Enrollment Period?",
             "type": "boolean", "required": True,
             "description": "Special enrollment is triggered by life events: job loss, marriage, birth, moving, etc."},
        ],
        "determination_received": [
            {"key": "all_determinations_in",
             "label": "Have all benefit determinations been received from the agencies?",
             "type": "boolean", "required": True,
             "description": "Mark Yes only after every program (Medicaid, CHIP, ACA, etc.) has responded."},
        ],
        "determination_router": [
            {"key": "any_denied",
             "label": "Was any benefit application denied?",
             "type": "boolean", "required": True},
        ],
    },
    "charity_care_navigator": {
        "fpl_tier_check": [
            {"key": "income_fpl_percent",
             "label": "Patient household income as % of Federal Poverty Level",
             "type": "number", "required": True,
             "description": "Use the household income calculator. Enter 100 for 100% of FPL, 200 for 200%, etc."},
        ],
        "sliding_scale_check": [
            {"key": "income_fpl_percent",
             "label": "Patient household income as % of Federal Poverty Level",
             "type": "number", "required": True,
             "description": "Use the household income calculator. Enter 100 for 100% of FPL, 200 for 200%, etc."},
        ],
        "determination": [
            {"key": "determination_status",
             "label": "What did the hospital decide on the charity care application?",
             "type": "select", "required": True,
             "options": [
                 {"value": "approved_full", "label": "Approved - full write-off"},
                 {"value": "approved_partial", "label": "Approved - partial discount"},
                 {"value": "denied", "label": "Denied"},
                 {"value": "pending", "label": "Still pending"},
             ]},
        ],
        "appeal_outcome": [
            {"key": "appeal_status",
             "label": "What was the outcome of the appeal?",
             "type": "select", "required": True,
             "options": [
                 {"value": "overturned", "label": "Overturned - appeal won"},
                 {"value": "upheld", "label": "Upheld - appeal denied"},
                 {"value": "pending", "label": "Still pending"},
             ]},
        ],
        "remaining_balance_check": [
            {"key": "remaining_balance",
             "label": "Remaining balance the patient still owes after charity care",
             "type": "currency", "required": True,
             "description": "Enter 0 if the bill is fully resolved."},
        ],
    },
    "community_resource_router": {
        "barrier_loop_check": [
            {"key": "retry_count",
             "label": "How many times has the patient tried to engage with this resource so far?",
             "type": "number", "required": True,
             "description": "Enter 0 for first attempt. Up to 2 retries are allowed before escalation."},
        ],
    },
    "debt_cancellation_engine": {
        "request_itemized": [
            {"key": "is_itemized",
             "label": "Does the patient have an itemized bill?",
             "type": "boolean", "required": True,
             "description": "An itemized bill lists each charge separately. If they only have a summary, mark No and the workflow will request one."},
        ],
        "sol_check": [
            {"key": "within_sol",
             "label": "Is the debt still within the statute of limitations in this state?",
             "type": "boolean", "required": True,
             "description": "Most states have 3-6 year SOLs for medical debt. If unsure, ask the AI Concierge or check the state rule lookup."},
        ],
        "violations_found": [
            {"key": "violations_count",
             "label": "How many billing violations did the audit find?",
             "type": "number", "required": True,
             "description": "Enter 0 if no violations were found. Common violations: balance billing, NSA violations, duplicate charges."},
        ],
        "no_violation_router": [
            {"key": "hardship_indicated",
             "label": "Is the patient experiencing financial hardship?",
             "type": "boolean", "required": True,
             "description": "Hardship triggers: unable to afford basic needs, recent job loss, disability, on public benefits."},
        ],
        "negotiation_continue": [
            {"key": "negotiation_round_count",
             "label": "How many negotiation rounds have happened so far?",
             "type": "number", "required": True,
             "description": "Enter 0 for the first round. Up to 3 rounds are allowed before escalation."},
        ],
        "remaining_balance_check": [
            {"key": "remaining_balance",
             "label": "Remaining balance after the negotiation",
             "type": "currency", "required": True,
             "description": "Enter 0 if the debt is fully resolved."},
        ],
    },
    "insurance_appeal_assistant": {
        "deadline_check": [
            {"key": "days_remaining",
             "label": "How many days remain to file the appeal?",
             "type": "number", "required": True,
             "description": "Found on the denial letter. Most insurers give 30, 60, or 180 days from the date of denial."},
        ],
    },
    "master_case_orchestrator": {
        "cross_module_dependency_check": [
            {"key": "dependencies_resolved",
             "label": "Are all cross-module dependencies resolved?",
             "type": "boolean", "required": True,
             "description": "Yes if every prerequisite from upstream modules has been completed."},
        ],
        "all_modules_complete_check": [
            {"key": "all_modules_complete",
             "label": "Have all dispatched modules finished running?",
             "type": "boolean", "required": True,
             "description": "Wait until each invoked module has reached a terminal state."},
        ],
        "exception_check": [
            {"key": "exception_count",
             "label": "How many module exceptions or failures occurred?",
             "type": "number", "required": True,
             "description": "Enter 0 if every module finished cleanly."},
        ],
    },
}


def main():
    dirs = [Path("src/cen/modules"), Path("CEN_modules_v2")]
    total_added = 0
    for module, node_edits in EDITS.items():
        for d in dirs:
            p = d / f"{module}.json"
            if not p.exists():
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            modified = False
            for node in data["nodes"]:
                if node["id"] in node_edits:
                    node.setdefault("metadata", {})
                    if "input_schema" not in node["metadata"]:
                        node["metadata"]["input_schema"] = node_edits[node["id"]]
                        modified = True
                        total_added += 1
                        print(f"  + {p.parent.name}/{p.name} :: {node['id']}")
            if modified:
                p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"\nDone. Added {total_added} input_schema entries.")


if __name__ == "__main__":
    main()
