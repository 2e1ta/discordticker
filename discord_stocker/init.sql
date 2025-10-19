CREATE TABLE IF NOT EXISTS portfolio (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    purchase_price DOUBLE PRECISION NOT NULL,
    quantity INT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
