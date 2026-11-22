"""Receive exact specialist findings at internal commands after their native authorization checks."""
from apps.workflows.native_stations import receive_advice


def accept(actor, case, subject, *processes):
    for process in processes:
        receive_advice(process, subject, actor, case=case)


def planning_exit(actor, dossier, snapshot):
    by_kind = {"ui_applicability":"P22","ui_design":"P22","ui_client":"P22",
               "technical_design":"P23","test_strategy":"P24","uat_approach":"P24"}
    pins = [pin[0] for kind,pin in snapshot["sources"].items() if kind in by_kind]
    for source in dossier.sources.filter(pk__in=pins):
        accept(actor,dossier.case,source,by_kind[source.kind])


def release_readiness(actor, dossier, upstream):
    for gate in dossier.candidate.gates.filter(pk__in=[pin[0] for pin in upstream["gates"]]):
        process = {"qa_exit":"P29","engineering_go":"P31"}.get(gate.kind,"P30")
        accept(actor,dossier.case,gate,process)


def publication(actor, version):
    from apps.documents.contracts import PMO_DOCUMENT_TYPES
    from .models import CommercialDocumentBinding, MinutesReportBinding
    if version.template.definition["document_type"] not in PMO_DOCUMENT_TYPES:
        return
    case = version.document.case
    accept(actor,case,version,"P52","P53")
    statement = CommercialDocumentBinding.objects.filter(version=version).first()
    if statement:
        accept(actor,case,statement,"P01")
    report = MinutesReportBinding.objects.filter(version=version,report__isnull=False).first()
    if report:
        accept(actor,case,report,"P04")
