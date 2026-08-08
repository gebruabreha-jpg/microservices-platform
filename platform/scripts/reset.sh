#!/bin/bash
cd "$(dirname "$0")/.."
docker compose down -v
echo "All services stopped and volumes removed."
