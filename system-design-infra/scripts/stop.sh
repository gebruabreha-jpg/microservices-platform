#!/bin/bash
cd "$(dirname "$0")/.."
docker compose -f system-design-infra/docker-compose.yml down
echo "All infrastructure services stopped."