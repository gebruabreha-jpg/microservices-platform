CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50),
    order_id INTEGER,
    status VARCHAR(50) DEFAULT 'queued',
    created_at TIMESTAMP DEFAULT NOW()
);
