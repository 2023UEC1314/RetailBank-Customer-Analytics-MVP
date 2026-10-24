# Architecture

```text
Sources (CSV/JSON)
        |
        v
S3 Raw/Bronze -- immutable/audit
        |
        v
AWS Glue + PySpark
        |
   +----+----+
   |         |
   v         v
DQ/Transform  Quarantine
   |
   v
Curated Star Schema
   |
   +--> DIM_CUSTOMER (SCD2)
   +--> DIM_PRODUCT
   +--> DIM_BRANCH
   +--> FACT_TRANSACTION
              |
              v
         Redshift
              |
              v
          13 KPIs
```

Day 2:
- New dimension -> insert
- Changed dimension -> close old SCD2 version + insert new version
- Corrected transaction -> update existing fact by transaction_id
- New transaction -> insert
