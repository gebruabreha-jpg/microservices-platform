CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER,
    product_id INTEGER,
    quantity INTEGER,
    amount DECIMAL(10,2),
    status VARCHAR(50) DEFAULT 'created'
);
