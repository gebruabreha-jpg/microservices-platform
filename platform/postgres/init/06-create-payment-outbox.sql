-- Transactional outbox for payment-service (relayed to RabbitMQ "notifications" queue).
CREATE TABLE IF NOT EXISTS payment_outbox (
    id BIGSERIAL PRIMARY KEY,
    topic VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_payment_outbox_unpublished
    ON payment_outbox (id) WHERE published_at IS NULL;
