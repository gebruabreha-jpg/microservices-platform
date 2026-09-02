#!/bin/bash
# Pre-create Kafka topics with explicit partition counts (don't rely on
# auto-create, which uses num.partitions=1 and races the first producer).
set -e

BOOTSTRAP="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"

kafka-topics --create --if-not-exists --topic orders \
  --bootstrap-server "$BOOTSTRAP" --partitions 3 --replication-factor 1

echo "Kafka topics ready."
