-- KPI 1: Top 5 customers by net transaction volume
SELECT customer_id,
       SUM(CASE WHEN is_refund THEN -ABS(amount) ELSE ABS(amount) END) AS net_transaction_volume,
       COUNT(*) AS transaction_count
FROM fact_transaction
GROUP BY customer_id
ORDER BY net_transaction_volume DESC, transaction_count DESC
LIMIT 5;

-- KPI 2: Monthly transaction trend by branch
WITH m AS (
  SELECT branch_id,
         DATE_TRUNC('month', transaction_date) AS month,
         SUM(CASE WHEN is_refund THEN -ABS(amount) ELSE ABS(amount) END) AS value
  FROM fact_transaction
  GROUP BY 1,2
)
SELECT *, LAG(value) OVER(PARTITION BY branch_id ORDER BY month) AS previous_value,
       CASE WHEN LAG(value) OVER(PARTITION BY branch_id ORDER BY month) = 0 THEN NULL
            ELSE (value-LAG(value) OVER(PARTITION BY branch_id ORDER BY month))
                 / ABS(LAG(value) OVER(PARTITION BY branch_id ORDER BY month))*100 END AS mom_growth_pct
FROM m;

-- KPI 3: Product revenue contribution
WITH p AS (
  SELECT product_id,
         SUM(CASE WHEN is_refund THEN -ABS(amount) ELSE ABS(amount) END) AS revenue
  FROM fact_transaction GROUP BY product_id
)
SELECT product_id, revenue,
       revenue / NULLIF(SUM(revenue) OVER(),0) * 100 AS revenue_share_pct
FROM p;

-- KPI 5: High-value/suspicious transactions
SELECT *,
       CASE
         WHEN amount > 100000 THEN 'HIGH_VALUE'
         WHEN EXTRACT(HOUR FROM transaction_date) BETWEEN 0 AND 4 THEN 'NIGHT_TRANSACTION'
         ELSE 'REVIEW'
       END AS risk_reason
FROM fact_transaction
WHERE amount > 100000
   OR EXTRACT(HOUR FROM transaction_date) BETWEEN 0 AND 4;

-- KPI 8: KYC risk exposure
SELECT
  SUM(CASE WHEN c.kyc_status <> 'Verified' THEN ABS(f.amount) ELSE 0 END) AS non_verified_value,
  SUM(ABS(f.amount)) AS total_value,
  SUM(CASE WHEN c.kyc_status <> 'Verified' THEN ABS(f.amount) ELSE 0 END)
    / NULLIF(SUM(ABS(f.amount)),0) * 100 AS non_verified_value_pct
FROM fact_transaction f
JOIN dim_customer c ON f.customer_key = c.customer_key;
