# RetailBank – Customer Transaction Analytics

## Objective
Build an auditable retail-bank data pipeline that ingests raw CSV/JSON data, performs data-quality validation and quarantine, creates a curated star schema, generates banking KPIs, and processes Day 2 incremental changes using SCD Type 2 and transaction upserts.

## Stack
- Python / Pandas for the fast local MVP
- PySpark/AWS Glue for the cloud implementation
- Amazon S3 for raw/bronze
- Amazon Redshift for curated analytics
- SQL for KPIs
- Git/GitHub for version control

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
```

Put the Day 1 files in `data/day1/`:
- branches.csv
- customers.csv
- products.json
- transactions.csv

Then:

```bash
python src/pipeline.py
```

Outputs:
- `output/reports/data_profile.csv`
- `output/reports/dq_scorecard.csv`
- `output/quarantine/transactions.csv`
- `output/curated/dim_customer.csv`
- `output/curated/dim_product.csv`
- `output/curated/dim_branch.csv`
- `output/curated/fact_transaction.csv`
- `output/kpis/`

For Day 2, place:
- branches_day2.csv
- customer_updates_day2.csv
- products_day2.json
- transactions_day2.csv

Then:

```bash
python src/day2_incremental.py
```

## Grain
`fact_transaction`: one row = one transaction.

## Day 2 logic
- New dimension record -> INSERT
- Business-meaningful dimension change -> SCD Type 2
- Existing transaction correction -> UPDATE by transaction_id
- New transaction -> INSERT
- Invalid records -> quarantine with reason_code
- Pipeline should be safely rerunnable/idempotent.

## AWS mapping

S3 Raw/Bronze -> AWS Glue/PySpark -> S3 Curated/Quarantine -> Redshift -> KPI SQL.

## Demo flow
1. Show raw messy records.
2. Show DQ profile.
3. Show quarantine with reason codes.
4. Show star schema.
5. Show KPI outputs.
6. Introduce Day 2 customer KYC change.
7. Show two SCD2 customer versions.
8. Introduce corrected transaction.
9. Show update without duplicate.
10. Show KPI delta.

# Retail Bank Customer Transaction Analytics MVP

## 1. Problem Statement

## 2. Solution Overview

## 3. Architecture

## 4. AWS Cloud Mapping

## 5. Data Sources

### Day 1
### Day 2

## 6. Data Quality

## 7. Data Model

### DIM_CUSTOMER
### DIM_PRODUCT
### DIM_BRANCH
### FACT_TRANSACTION

## 8. SCD Type 2

## 9. Day 2 Incremental Processing

## 10. Transaction Corrections

## 11. Idempotency

## 12. KPI Layer

## 13. Dashboard

## 14. Project Structure

## 15. Setup Instructions

## 16. How to Run

## 17. Validation Results

## 18. AWS Production Architecture

## 19. Future Enhancements