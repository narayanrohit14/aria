#!/usr/bin/env bash

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

pass_count=0

print_result() {
  local status="$1"
  local label="$2"

  if [[ "$status" == "PASS" ]]; then
    pass_count=$((pass_count + 1))
  fi

  printf '%s: %s\n' "$status" "$label"
}

check_directories() {
  local required_dirs=(
    "frontend"
    "backend/api"
    "backend/agent"
    "backend/data"
    "ml"
    "infra/docker"
  )
  local missing=()
  local dir

  for dir in "${required_dirs[@]}"; do
    if [[ ! -d "${REPO_ROOT}/${dir}" ]]; then
      missing+=("$dir")
    fi
  done

  if [[ ${#missing[@]} -eq 0 ]]; then
    print_result "PASS" "Required directories exist"
  else
    print_result "FAIL" "Required directories exist (missing: ${missing[*]})"
  fi
}

check_files() {
  local required_files=(
    "docker-compose.yml"
    ".env.example"
    ".gitignore"
    "backend/api/main.py"
    "backend/api/requirements.txt"
    "backend/agent/agent.py"
    "backend/data/aria_data_ingestion.py"
    "infra/docker/Dockerfile.api"
    "infra/docker/Dockerfile.frontend"
    "frontend/app/page.tsx"
  )
  local missing=()
  local file

  for file in "${required_files[@]}"; do
    if [[ ! -f "${REPO_ROOT}/${file}" ]]; then
      missing+=("$file")
    fi
  done

  if [[ ${#missing[@]} -eq 0 ]]; then
    print_result "PASS" "Required files exist"
  else
    print_result "FAIL" "Required files exist (missing: ${missing[*]})"
  fi
}

check_env_file() {
  if [[ -f "${REPO_ROOT}/.env" ]]; then
    print_result "PASS" ".env file exists"
  else
    print_result "FAIL" ".env file exists"
  fi
}

check_docker() {
  if docker info >/dev/null 2>&1; then
    print_result "PASS" "Docker is running"
  else
    print_result "FAIL" "Docker is running"
  fi
}

check_port_free() {
  local port="$1"
  local service_name="$2"

  if lsof -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
    print_result "FAIL" "Port ${port} is available for ${service_name}"
  else
    print_result "PASS" "Port ${port} is available for ${service_name}"
  fi
}

echo "Validating Phase 1 setup in ${REPO_ROOT}"

check_directories
check_files
check_env_file
check_docker
check_port_free 5432 "Postgres"
check_port_free 6379 "Redis"
check_port_free 8000 "FastAPI"
check_port_free 3000 "Next.js"

printf '\n%d/8 checks passed.\n' "${pass_count}"

if [[ "${pass_count}" -eq 8 ]]; then
  echo "Phase 1 ready. Run: docker compose up postgres redis"
else
  echo "Fix the above issues before proceeding."
fi
