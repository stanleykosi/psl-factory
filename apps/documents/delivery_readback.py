"""Read the result of an authorized original publication without another send."""
from django.contrib.auth import get_user_model


def recipient_rows(job, version, receipts):
    if not job or job.publication.version_id != version.pk:
        return []
    people = get_user_model().objects.in_bulk(job.publication.recipient_ids)
    originals = {receipt.recipient_id: receipt for receipt in receipts
                 if receipt.publication_id == job.publication_id
                 and receipt.payload_sha256 == version.payload_sha256 and receipt.payload == version.payload}
    outstanding = {'pending': 'Waiting to send', 'unknown': 'Delivery uncertain', 'held': 'Delivery needs review',
                   'leased': 'Checking delivery', 'cancelled': 'Cancelled'}.get(job.status, 'Receipt unavailable')
    rows = []
    for key in job.publication.recipient_ids:
        person, receipt = people.get(key), originals.get(key)
        status = outstanding
        if receipt:
            status = 'Delivered' if job.status == 'confirmed' else 'Original receipt found'
        rows.append({'recipient': (person.get_full_name() or person.get_username()) if person else 'Recorded recipient',
                     'status': status, 'at': receipt.created_at if receipt else None, 'receipt': receipt})
    return rows
