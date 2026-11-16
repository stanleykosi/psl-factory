#!/bin/sh
set -eu

until python manage.py migrate --check; do
    sleep 10
done

while true; do
    python manage.py work_outbox --limit 20
    python manage.py work_publications --limit 20
    python manage.py work_invoices --limit 20
    python manage.py work_payment_reminders
    python manage.py work_approval_routes --limit 20
    python manage.py work_agent_uploads
    python manage.py work_assistant
    python manage.py work_factory_progress
    sleep 30
done
