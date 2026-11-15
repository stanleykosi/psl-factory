FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock requirements.deploy.txt ./
RUN pip install --no-cache-dir -r requirements.lock -r requirements.deploy.txt
COPY apps apps
COPY adapters adapters
COPY config config
COPY contracts contracts
COPY fixtures fixtures
COPY reference reference
COPY static static
COPY templates templates
COPY manage.py SOURCE-MANIFEST.json ./
COPY scripts/railway-worker.sh /app/railway-worker.sh
RUN PSL_ENV=development python manage.py collectstatic --noinput && mkdir -p /app/.runtime
CMD ["sh", "-c", "if [ \"$PSL_SERVICE_ROLE\" = worker ]; then exec sh /app/railway-worker.sh; fi; python manage.py migrate --noinput && { [ -z \"$PSL_AGENT_TRIAL_PASSWORD\" ] || python manage.py provision_agent_trial; } && { [ \"$PSL_AGENT_TRIAL_WORKFLOWS\" != 1 ] || python manage.py prepare_agent_trial_workflows; } && { [ \"$PSL_AGENT_TRIAL_OUTCOMES\" != 1 ] || python manage.py check_agent_trial_outcomes; } && exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 2 --access-logfile - --error-logfile -"]
