#!/usr/bin/env bash
# Verifies THIS worktree's local Postgres is isolated and running correctly.
# Self-detecting: reads the port/project name straight out of docker-compose.yml,
# so this exact same script works unmodified in every worktree.
set -uo pipefail

cd "$(dirname "$0")/.."

PROJECT=$(grep -m1 '^name:' docker-compose.yml | awk '{print $2}')
PORT=$(grep -m1 -oE '"[0-9]+:5432"' docker-compose.yml | grep -oE '[0-9]+' | head -1)
CONTAINER="${PROJECT}-postgres-1"

echo "This worktree ($(basename "$(pwd)")) expects:"
echo "  compose project : $PROJECT"
echo "  container name  : $CONTAINER"
echo "  host port       : $PORT"
echo

STATUS=$(docker ps --filter "name=^${CONTAINER}$" --format '{{.Status}}')
if [ -z "$STATUS" ]; then
  echo "Container is NOT running."
  echo "  -> run: docker compose up -d"
  exit 1
fi
echo "OK  container running: $STATUS"

if [ ! -f .env ]; then
  echo "WARN  no .env file found in this worktree"
  exit 1
fi

ENV_PORT=$(grep -oE 'localhost:[0-9]+' .env | head -1 | grep -oE '[0-9]+')
if [ "$ENV_PORT" != "$PORT" ]; then
  echo "MISMATCH  .env points at port $ENV_PORT but docker-compose.yml uses $PORT"
  echo "  -> this worktree's app would be talking to the wrong database (or none)"
  exit 1
fi
echo "OK  .env port matches ($ENV_PORT)"

echo
echo "All good -- this worktree is correctly isolated and ready."
