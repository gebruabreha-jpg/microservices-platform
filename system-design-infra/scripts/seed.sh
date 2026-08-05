#!/bin/bash
cd "$(dirname "$0")/.."
echo "Seeding PostgreSQL..."
docker compose -f system-design-infra/docker-compose.yml exec -T postgres psql -U admin -d appdb -c "
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER,
    product_id INTEGER,
    quantity INTEGER,
    amount DECIMAL(10,2),
    status VARCHAR(50) DEFAULT 'created'
);
INSERT INTO orders (customer_id, product_id, quantity, amount, status) VALUES (1, 1, 2, 59.98, 'created');
" 2>/dev/null

echo "Seeding Redis..."
docker compose -f system-design-infra/docker-compose.yml exec -T redis redis-cli SET sample:key "hello" 2>/dev/null

echo "Seeding complete."