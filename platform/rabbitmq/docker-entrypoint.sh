#!/bin/sh
set -e

# Wait for RabbitMQ to be ready
until rabbitmqctl status > /dev/null 2>&1; do
  echo "Waiting for RabbitMQ to start..."
  sleep 2
done

# Import definitions if file exists
if [ -f /etc/rabbitmq/definitions.json ]; then
  echo "Importing RabbitMQ definitions..."
  rabbitmqctl import_definitions /etc/rabbitmq/definitions.json || true
fi

# Start RabbitMQ
exec rabbitmq-server
