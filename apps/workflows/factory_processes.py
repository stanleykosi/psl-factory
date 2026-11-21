"""Source process for each native station. Only the native observation selects a route."""

from django.core.exceptions import ValidationError

STATIC = {
    "pmo-issues/v1": "P50",
    "finance-ledger/v1": "F01",
    "pmo-minutes/v1": "P43",
    "pmo-escalation/v1": "P44",
    "pmo-weekly-report/v1": "P41",
    "finance-ppe/v1": "F07",
    "finance-forecast/v1": "F39",
    "delivery-go-live/v1": "P33",
    "delivery-closure/v1": "P39",
    "delivery-handover/v1": "P37",
    "delivery-archive/v1": "P36",
    "delivery-hypercare/v1": "P35",
    "delivery-release/v1": "P32",
    "planning/v1": "P26",
}

PROCESS_IDS = {
    **{line: (process,) for line, process in STATIC.items()},
    "delivery-release/v1": ("P32", "P28"),
    "finance-bu/v1": ("F21", "F44"),
    "engagement/v1": ("P16", "P03"),
    "pmo-leadership-report/v1": ("P40", "P42"),
    "finance-schedules/v1": ("F12", "F13"),
    "finance-payroll/v1": ("F16", "F17", "F18"),
    "pmo-emergency/v1": ("P61", "P62"),
    "pmo-change/v1": ("P57", "P59", "P60"),
    "finance-accounts/v1": ("F03", "F22", "F09", "F23"),
    "rfp-response/v1": ("P46", "P47", "P48", "P49"),
    "commercial/v1": ("P14", "P06", "P07"),
    "pmo-finance/v1": ("P34", "F29", "F30"),
}


def process_for(work, activity, observed, profile):
    line = work.definition
    if line in STATIC:
        return STATIC[line]
    if line == "finance-bu/v1":
        return "F21" if work.request.get("mode") == "staff" else "F44"
    if line == "engagement/v1":
        return "P16" if activity == "ACT04" else "P03"
    if line == "pmo-leadership-report/v1":
        return "P40" if work.request.get("kind") == "internal_tuesday" else "P42"
    if line == "finance-schedules/v1":
        return "F12" if work.request.get("kind") == "income" else "F13"
    if line == "finance-payroll/v1":
        stage = observed["native"]["stage"]
        if stage in ("aggregate", "aggregate_review", "publish", "receipt", "complete"):
            return "F18"
        return "F17" if stage in ("match", "match_review") else "F16"
    if line == "pmo-emergency/v1":
        return "P62" if observed["native"]["outcome"] else "P61"
    if line == "pmo-change/v1":
        if activity == "ACT04":
            return "P57"
        return "P60" if observed["native"]["stage"] in ("go_live", "signatures", "complete") else "P59"
    if line == "finance-accounts/v1":
        from .factory_accounting import process_for_activity

        return process_for_activity(activity, observed, profile)
    if line == "rfp-response/v1":
        if activity == "ACT04":
            return "P46"
        if not observed["document"]:
            return "P47"
        return "P49" if observed["submission"] else "P48"
    if line == "commercial/v1":
        return {"ACT04": "P14", "ACT08": "P06"}.get(activity, "P07")
    if line == "pmo-finance/v1":
        if activity == "ACT08":
            return "F29"
        return "F30" if activity in ("ACT09", "ACT10", "ACT11", "ACT12", "ACT13") else "P34"
    raise ValidationError("This workflow needs a registered native process route.")
