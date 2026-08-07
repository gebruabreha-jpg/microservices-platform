CREATE TABLE IF NOT EXISTS inventory (
    id SERIAL PRIMARY KEY,
    product_id INTEGER,
    quantity INTEGER,
    reserved INTEGER DEFAULT 0
);
