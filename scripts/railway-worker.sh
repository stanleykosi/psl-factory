#!/bin/sh
set -eu

export PSL_OPENROUTER_COORDINATION=${PSL_OPENROUTER_COORDINATION:-1}

until python manage.py migrate --check; do
    sleep 10
done

run_child() {
    "$@" &
    child=$!
    wait "$child"
    child=
}

poll() {
    child=
    trap 'if [ -n "$child" ]; then kill "$child" 2>/dev/null || true; wait "$child" || true; fi; exit 0' TERM INT
    while true; do
        "$1"
        run_child sleep 30
    done
}

effects() {
    run_child python manage.py work_outbox --limit 20
    run_child python manage.py work_publications --limit 20
    run_child python manage.py work_archive_files --limit 10
    run_child python manage.py work_invoices --limit 20
    run_child python manage.py work_payment_reminders
    run_child python manage.py work_rfp_followup
    run_child python manage.py work_issue_messages --limit 20
    run_child python manage.py work_account_delivery --limit 20
    run_child python manage.py work_approval_routes --limit 20
}

progress() {
    run_child python manage.py work_native_stations --limit 20
    run_child python manage.py work_factory_progress
}

uploads() {
    run_child python manage.py work_agent_uploads
}

assistant() {
    run_child python manage.py work_assistant
}

python manage.py work_specialist_readings --watch &
source_worker=$!
poll effects &
effect_worker=$!
poll progress &
progress_worker=$!
poll uploads &
upload_worker=$!
poll assistant &
assistant_worker=$!

workers="$source_worker $effect_worker $progress_worker $upload_worker $assistant_worker"
trap 'kill $workers 2>/dev/null || true; wait || true' EXIT
trap 'exit 0' TERM INT
while true; do
    for runner in "specialist:$source_worker" "effects:$effect_worker" "progress:$progress_worker" \
                  "uploads:$upload_worker" "assistant:$assistant_worker"; do
        if ! kill -0 "${runner#*:}" 2>/dev/null; then
            echo "The ${runner%:*} runner stopped. Restarting the worker service." >&2
            exit 1
        fi
    done
    sleep 3
done
