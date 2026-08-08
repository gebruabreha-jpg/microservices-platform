CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    order_id INTEGER,
    amount DECIMAL(10,2),
    status VARCHAR(50) DEFAULT 'processing'
);
