-- KPI 11: Day 2 reconciliation
-- Compare counts/sums between Day 1 snapshot and current fact table.
SELECT COUNT(*) AS current_transaction_count,
       SUM(amount) AS current_transaction_value
FROM fact_transaction;

-- KPI 12: KYC transitions / SCD2
SELECT customer_id,
       MIN(CASE WHEN kyc_status <> 'Verified' THEN effective_from END) AS prior_status_from,
       MAX(CASE WHEN kyc_status = 'Verified' THEN effective_from END) AS verified_from
FROM dim_customer
GROUP BY customer_id
HAVING COUNT(*) > 1;

-- KPI 13: New account activation
SELECT customer_id, MIN(transaction_date) AS first_transaction_date
FROM fact_transaction
GROUP BY customer_id;
