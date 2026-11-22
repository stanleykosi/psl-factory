#!/bin/sh
set -eu

if [ "${RAILWAY_ENVIRONMENT_NAME:-}" != design-acceptance ] ||
   [ "${RAILWAY_PROJECT_ID:-}" != f957481b-c6f7-43af-bc66-449a330a9d53 ]; then
    echo 'The browser sample pack requires the Railway acceptance project and environment.' >&2
    exit 1
fi

case "${PGDATABASE:-}" in
    ''|test_*) echo 'The preview application database must be explicitly configured.' >&2; exit 1 ;;
esac

python manage.py migrate --noinput
PSL_COMPOSED_WALKTHROUGH=1 PSL_COMMERCIAL_CLIENT_FIXTURE=1 \
    python manage.py shell -c 'from tests.railway_batch_walkthrough_seed import run; run()'
echo 'PSL_PREVIEW_SAMPLES_EXIT=0'
