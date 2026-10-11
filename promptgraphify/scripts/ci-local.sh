#!/usr/bin/env bash
# The steps of ../.github/workflows/promptgraphify-ci.yml (repository root), run on this machine. Usage: scripts/ci-local.sh [--skip-e2e] [--skip-docker]
# Exit code is non-zero at the first failing step; the Docker step is skipped (and says so) if no daemon is reachable.
set -euo pipefail
cd "$(dirname "$0")/.."
skip_e2e=0; skip_docker=0
for a in "$@"; do case "$a" in --skip-e2e) skip_e2e=1;; --skip-docker) skip_docker=1;; *) echo "unknown option $a" >&2; exit 2;; esac; done
step() { printf '\n== %s\n' "$*"; }

step "backend: uv sync --frozen"; uv sync --frozen
step "backend: ruff check"; uv run ruff check src tests
step "backend: ruff format --check"; uv run ruff format --check src tests
step "backend: pytest"; uv run pytest -q
step "requirements.txt matches uv.lock"
uv export --no-dev --no-emit-project --frozen --format requirements-txt -o /tmp/pg-requirements.txt
diff <(grep -v '^#' requirements.txt) <(grep -v '^#' /tmp/pg-requirements.txt) && echo "in sync"

step "web: npm ci"; (cd web && npm ci)
step "web: tsc"; (cd web && npx tsc --noEmit)
step "web: vitest"; (cd web && npx vitest run)
if [ "$skip_e2e" = 1 ]; then echo "(e2e skipped by request)"; else
  step "web: playwright"; (cd web && npx playwright test)
fi

if [ "$skip_docker" = 1 ]; then echo "(docker skipped by request)"
elif docker info >/dev/null 2>&1; then
  step "docker: api"; docker build --target api -t promptgraphify-api .
  step "docker: web"; docker build --target web -t promptgraphify-web --build-arg PROMPTGRAPHIFY_API_URL=http://api:8000 .
else
  echo; echo "SKIPPED docker: no daemon is reachable ('docker info' failed), so the images were NOT built here." >&2
fi
echo; echo "ci-local: all executed steps passed"
