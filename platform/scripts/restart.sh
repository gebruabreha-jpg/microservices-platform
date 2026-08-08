#!/bin/bash
cd "$(dirname "$0")/.."
docker compose restart
echo "All platform services restarted."
