#!/bin/bash
set -e

echo "Running order-service tests..."
cd services/order-service && python -m pytest tests/ -v

echo "Running payment-service tests..."
cd services/payment-service && python -m pytest tests/ -v

echo "Running notification-service tests..."
cd services/notification-service && python -m pytest tests/ -v

echo "All tests passed."
