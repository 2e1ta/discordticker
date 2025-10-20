CREATE TABLE IF NOT EXISTS portfolio (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    purchase_price DOUBLE PRECISION NOT NULL,
    quantity INT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE portfolio
    ADD COLUMN IF NOT EXISTS guild_id BIGINT;
