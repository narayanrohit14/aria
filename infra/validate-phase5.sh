#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS_COUNT=0

check_pass() {
  local label="$1"
  echo "PASS: ${label}"
  PASS_COUNT=$((PASS_COUNT + 1))
}

check_fail() {
  local label="$1"
  echo "FAIL: ${label}"
}

check_file() {
  local path="$1"
  local label="$2"
  if [ -f "${ROOT_DIR}/${path}" ]; then
    check_pass "${label}"
  else
    check_fail "${label}"
  fi
}

check_file ".github/workflows/ci.yml" ".github/workflows/ci.yml exists"
check_file "infra/docker/Dockerfile.api.prod" "infra/docker/Dockerfile.api.prod exists"
check_file "infra/docker/Dockerfile.frontend.prod" "infra/docker/Dockerfile.frontend.prod exists"
check_file "railway.json" "railway.json exists"
check_file "Makefile" "Makefile exists"
check_file "DEPLOYMENT.md" "DEPLOYMENT.md exists"

BACKEND_TEST_COUNT="$(find "${ROOT_DIR}/backend/api/tests" -maxdepth 1 -type f -name 'test_*.py' | wc -l | tr -d ' ')"
if [ "${BACKEND_TEST_COUNT}" -ge 3 ]; then
  check_pass "backend/api/tests/ has at least 3 test files"
else
  check_fail "backend/api/tests/ has at least 3 test files"
fi

FRONTEND_TEST_COUNT="$(find "${ROOT_DIR}/frontend/__tests__" -type f -name '*.test.ts*' | wc -l | tr -d ' ')"
if [ "${FRONTEND_TEST_COUNT}" -ge 2 ]; then
  check_pass "frontend/__tests__/ has at least 2 test files"
else
  check_fail "frontend/__tests__/ has at least 2 test files"
fi

if (
  cd "${ROOT_DIR}/backend/api" &&
  ../../.venv/bin/python -m pytest tests/ >/tmp/aria-phase5-backend.log 2>&1
); then
  check_pass "backend tests pass"
else
  check_fail "backend tests pass"
  cat /tmp/aria-phase5-backend.log
fi

if (
  cd "${ROOT_DIR}/frontend" &&
  npm run test:ci >/tmp/aria-phase5-frontend.log 2>&1
); then
  check_pass "frontend tests pass"
else
  check_fail "frontend tests pass"
  cat /tmp/aria-phase5-frontend.log
fi

echo "${PASS_COUNT}/10 checks passed"

if [ "${PASS_COUNT}" -eq 10 ]; then
  echo "Phase 5 complete. ARIA is ready for deployment."
fi
