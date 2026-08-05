#!/bin/bash
cd "$(dirname "$0")/.."
docker compose -f system-design-infra/docker-compose.yml down -v
echo "All services stopped and volumes removed."