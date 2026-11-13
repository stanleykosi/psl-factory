#!/usr/bin/env bash
# PSL factory checks. Exit 0 only when the feature branch is fit to review.
#
# `feature.py gate` runs the main checkout's copy of this file with the feature's
# worktree as the working directory. Non-interactive and deterministic: no watch
# modes, no prompts, nothing that rewrites files.
#
# Backend: Django system check with the main checkout's virtualenv (fast; the full
# Django suite stays with backend tasks, run against PostgreSQL on port 55432).
# Frontend: once frontend/package.json exists, install from the lockfile, then lint,
# typecheck, unit tests and production build.
set -euo pipefail

MAIN="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)"
PY="${PSL_PYTHON:-$MAIN/.venv/bin/python}"

echo "== backend: django system check"
PGDATABASE="${PGDATABASE:-psl}" PGUSER="${PGUSER:-psl}" PGHOST="${PGHOST:-127.0.0.1}" PGPORT="${PGPORT:-55432}" PSL_ENV="${PSL_ENV:-development}" \
  "$PY" manage.py check

if [ -f frontend/package.json ]; then
  echo "== frontend: install, lint, typecheck, test, build"
  cd frontend
  npm ci --prefer-offline --no-audit --no-fund
  npm run lint
  npm run typecheck
  npm test --if-present
  npm run build
else
  echo "== frontend: not created yet (frontend/package.json missing); skipped"
fi
