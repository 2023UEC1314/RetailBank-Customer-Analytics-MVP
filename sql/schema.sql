-- Redshift/PostgreSQL-compatible curated model

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key BIGINT,
    customer_id VARCHAR(100),
    name VARCHAR(255),
    gender VARCHAR(50),
    email VARCHAR(255),
    phone VARCHAR(50),
    dob DATE,
    kyc_status VARCHAR(50),
    address VARCHAR(500),
    account_id VARCHAR(100),
    branch_id VARCHAR(100),
    product_id VARCHAR(100),
    effective_from DATE,
    effective_to DATE,
    is_current INTEGER
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_key BIGINT,
    product_id VARCHAR(100),
    product_name VARCHAR(255),
    category VARCHAR(100),
    price DECIMAL(18,2),
    is_active BOOLEAN,
    effective_from DATE,
    effective_to DATE,
    is_current INTEGER
);

CREATE TABLE IF NOT EXISTS dim_branch (
    branch_key BIGINT,
    branch_id VARCHAR(100),
    branch_name VARCHAR(255),
    region VARCHAR(100),
    branch_type VARCHAR(100),
    manager VARCHAR(255),
    phone VARCHAR(50),
    effective_from DATE,
    effective_to DATE,
    is_current INTEGER
);

CREATE TABLE IF NOT EXISTS fact_transaction (
    transaction_key BIGINT,
    transaction_id VARCHAR(100),
    customer_key BIGINT,
    product_key BIGINT,
    branch_key BIGINT,
    customer_id VARCHAR(100),
    product_id VARCHAR(100),
    branch_id VARCHAR(100),
    account_id VARCHAR(100),
    amount DECIMAL(18,2),
    currency VARCHAR(10),
    transaction_date TIMESTAMP,
    payment_method VARCHAR(100),
    status VARCHAR(50),
    is_refund BOOLEAN
);
