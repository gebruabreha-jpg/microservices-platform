CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    order_id INTEGER,
    amount DECIMAL(10,2),
    status VARCHAR(50) DEFAULT 'processing',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_payments_order_id ON payments (order_id);
