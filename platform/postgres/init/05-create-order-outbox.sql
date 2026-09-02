-- Transactional outbox for order-service (relayed to Kafka "orders" topic).
CREATE TABLE IF NOT EXISTS order_outbox (
    id BIGSERIAL PRIMARY KEY,
    topic VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_order_outbox_unpublished
    ON order_outbox (id) WHERE published_at IS NULL;
