#!/usr/bin/env bash
# PSL factory checks. Exit 0 only when the feature branch is fit to review.
#
# `feature.py gate` runs the project's copy of this file with the feature's
# worktree as the working directory. Non-interactive and deterministic: no watch
# modes, no prompts, nothing that rewrites files.
#
# Two modes (D-199):
#   ci     The default when the worktree has .github/workflows/frontend-checks.yml and
#          `gh` is signed in. Waits for GitHub's `frontend-checks` run on the exact pushed
#          HEAD commit and passes only if it succeeded. It runs the same steps as local mode,
#          on GitHub's runners, so gates don't queue on one machine.
#   local  Runs the steps here: the Django system check with the main checkout's virtualenv,
#          then frontend install, lint, typecheck, unit tests and production build.
# Force a mode with PSL_CHECKS_MODE=ci|local.
set -euo pipefail

MAIN="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)"
PY="${PSL_PYTHON:-$MAIN/.venv/bin/python}"
WORKFLOW=frontend-checks.yml

mode="${PSL_CHECKS_MODE:-}"
if [ -z "$mode" ]; then
  if [ -f ".github/workflows/$WORKFLOW" ] && command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
    mode=ci
  else
    mode=local
  fi
fi

if [ "$mode" = ci ]; then
  sha="$(git rev-parse HEAD)"
  echo "== ci: GitHub $WORKFLOW for $sha"
  git fetch -q origin 2>/dev/null || true
  if [ -z "$(git branch -r --contains "$sha" 2>/dev/null)" ]; then
    echo "HEAD $sha is not pushed; push the branch first (CI runs on pushed commits)." >&2
    exit 1
  fi
  deadline=$(( $(date +%s) + ${PSL_CI_TIMEOUT:-1700} ))
  seen_at=$(( $(date +%s) + 300 ))
  while :; do
    run="$(gh run list --commit "$sha" --workflow "$WORKFLOW" --event push -L 1 \
            --json databaseId,status,conclusion,url \
            -q '.[0] | "\(.databaseId) \(.status) \(.conclusion) \(.url)"' 2>/dev/null || true)"
    if [ -n "$run" ]; then
      read -r id status conclusion url <<<"$run"
      if [ "$status" = completed ]; then
        echo "run: $url"
        if [ "$conclusion" = success ]; then
          gh run view "$id" --json jobs -q '.jobs[].steps[] | "  \(.conclusion)  \(.name)"' 2>/dev/null || true
          echo "== ci: PASS"
          exit 0
        fi
        echo "== ci: $conclusion; failed step logs (tail):"
        gh run view "$id" --log-failed 2>/dev/null | tail -120 || true
        exit 1
      fi
    elif [ "$(date +%s)" -gt "$seen_at" ]; then
      echo "No $WORKFLOW run for $sha after 5 minutes (is the workflow on this branch, and was it pushed?)." >&2
      exit 1
    fi
    if [ "$(date +%s)" -gt "$deadline" ]; then
      echo "Timed out waiting for $WORKFLOW on $sha${run:+ ($run)}." >&2
      exit 124
    fi
    sleep 20
  done
fi

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
