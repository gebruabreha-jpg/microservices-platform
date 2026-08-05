#!/bin/bash
cd "$(dirname "$0")/.."
docker compose -f system-design-infra/docker-compose.yml up -d
echo "All infrastructure services started."