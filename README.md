# Retail Bank – Customer Transaction Analytics MVP

## 1. Problem Statement

Retail banking data arrives from multiple operational sources and may contain duplicate records, invalid values, missing references, inconsistent dates, and incremental corrections.

This project implements an auditable data pipeline that:

- Ingests Day 1 and Day 2 banking data
- Performs automated data-quality validation
- Quarantines invalid records with reason codes
- Builds curated dimensional and fact datasets
- Handles customer, product, and branch changes using SCD Type 2
- Handles transaction corrections without creating duplicates
- Supports idempotent Day 2 processing
- Generates business KPIs
- Provides a Streamlit analytics dashboard
- Maps the local MVP to an AWS production architecture

---

## 2. Solution Overview

The solution follows a layered architecture:

```text
Raw CSV / JSON
      |
      v
Data Ingestion
      |
      v
Data Quality Validation
      |
      +--------------------+
      |                    |
      v                    v
Cleansed Data          Quarantine
      |
      v
Curated Star Schema
      |
      +--------------------+
      |                    |
      v                    v
Dimensions              Fact
      |                Transactions
      +--------+---------+
               |
               v
          KPI / Analytics
               |
               v
        Streamlit Dashboard
```

The local implementation uses Python and Pandas. The production target architecture maps the same logical stages to AWS services.

---

## 3. Technology Stack

### Local MVP

- Python
- Pandas
- SQL
- Streamlit
- Git / GitHub

### Target AWS Architecture

- Amazon S3 – raw and curated data storage
- AWS Glue / PySpark – scalable ETL
- AWS Glue Data Quality – automated data-quality validation
- Amazon Redshift – curated analytics warehouse
- AWS Step Functions – workflow orchestration
- AWS Lambda – event-driven triggering
- SQL – KPI generation
- Streamlit / BI layer – analytics visualization

---

## 4. Data Sources

### Day 1

The initial batch contains:

- `branches.csv`
- `customers.csv`
- `products.json`
- `transactions.csv`

### Day 2

The incremental batch contains:

- `branches_day2.csv`
- `customer_updates_day2.csv`
- `products_day2.json`
- `transactions_day2.csv`

Day 2 introduces new records, dimension changes, duplicate records, transaction corrections, and invalid records.

---

## 5. Data Quality

The pipeline performs automated validation before records enter the curated layer.

Examples include:

- Missing required identifiers
- Invalid transaction dates
- Future transaction dates
- Invalid or non-positive amounts
- Invalid currencies
- Duplicate transaction IDs
- Duplicate records
- Missing customer references
- Missing product references
- Missing branch references
- Unresolved dimension references

Invalid records are not silently discarded.

They are written to the quarantine layer with a `reason_code`.

Example:

```text
INVALID_TRANSACTION_DATE
INVALID_AMOUNT
NON_POSITIVE_AMOUNT
DUPLICATE_TRANSACTION_ID
ORPHAN_CUSTOMER_ID
ORPHAN_PRODUCT_ID
ORPHAN_BRANCH_ID
UNRESOLVED_CUSTOMER_REFERENCE
```

This provides an auditable data-quality trail.

---

## 6. Curated Data Model

The curated layer follows a star-schema design.

### DIM_CUSTOMER

Stores customer attributes and their SCD Type 2 history.

Important fields include:

- customer surrogate key
- customer ID
- account ID
- customer attributes
- effective dates
- current-record indicator

### DIM_PRODUCT

Stores product information and product history.

### DIM_BRANCH

Stores branch information and branch history.

### FACT_TRANSACTION

The grain of the fact table is:

> One row = one transaction.

The fact contains transaction-level measures and foreign keys to the curated dimensions.

---

## 7. SCD Type 2

Business-meaningful dimension changes are handled using SCD Type 2.

When a customer or other dimension record changes:

```text
Old Version
    |
    | close previous version
    v
New Version
    |
    v
Current Record
```

Instead of overwriting the previous record, the pipeline preserves history and creates a new version.

This enables historical traceability while maintaining the current dimension state.

---

## 8. Day 2 Incremental Processing

The Day 2 pipeline does not perform a complete rebuild of the dataset.

It identifies:

- New dimension records
- Changed dimension records
- Unchanged dimension records
- New transactions
- Corrected transactions
- Duplicate records
- Invalid records

Example Day 2 processing result:

```text
New customers       : 19
Changed customers   : 16

New products        : 8
Changed products    : 9

New branches        : 1
Changed branches    : 1

New transactions    : 126
Corrected           : 5

Duplicate rows      : 2
Rejected records    : 64
```

This demonstrates incremental processing rather than full reprocessing.

---

## 9. Transaction Corrections

Existing transactions are identified using `transaction_id`.

When a correction version is received:

```text
Existing transaction
        |
        v
Match transaction_id
        |
        v
Apply corrected values
```

The pipeline updates the existing transaction instead of creating a second business transaction.

This prevents double counting.

---

## 10. Idempotency

The Day 2 pipeline is designed to be safely rerunnable.

A batch-processing marker prevents the exact same Day 2 input batch from being applied twice.

When the same batch is rerun:

```text
DAY 2 BATCH ALREADY PROCESSED

No duplicate SCD2 versions will be created.
No transaction corrections will be re-counted.
```

The final curated datasets therefore remain stable when the same batch is accidentally submitted again.

---

## 11. KPI Layer

The pipeline generates KPI outputs for business analysis.

### Day 2 Change KPIs

```text
New customers
Changed customers

New products
Changed products

New branches
Changed branches
```

### Transaction KPIs

```text
New transactions
Corrected transactions
```

### Overall Transaction KPIs

The official Day 2 KPI output records:

```text
Total transaction count  : 567
Total transaction amount : 54,150,035
Refund transaction count : 44
```

The KPI layer is separated from the curated datasets so that business metrics can be consumed independently.

---

## 12. Data Quality Results

The final manually validated curated fact contains:

```text
FACT ROWS              : 549
UNIQUE TRANSACTION IDs : 549
DUPLICATE TRANSACTION IDs : 0
NULL CUSTOMER KEYS     : 0
NULL PRODUCT KEYS      : 0
NULL BRANCH KEYS       : 0
```

The quarantine layer preserves rejected records and their validation reasons.

This allows reviewers to inspect both accepted and rejected data.

---

## 13. Dashboard

A Streamlit dashboard provides an interactive view of:

- Executive KPIs
- Transaction analytics
- Customer and product information
- Data-quality results
- Day 2 incremental changes

Dashboard sections include:

```text
Executive Overview
Transactions
Customers & Products
Data Quality
Day 2 Incremental
```

Run the dashboard with:

```bash
streamlit run dashboard.py
```

---

## 14. Project Structure

```text
RetailBank-Customer-Analytics-MVP/
│
├── data/
│   ├── day1/
│   └── day2/
│
├── src/
│   ├── pipeline.py
│   └── day2_incremental.py
│
├── sql/
│   ├── schema.sql
│   ├── kpi_day1.sql
│   └── kpi_day2.sql
│
├── output/
│   ├── curated/
│   ├── quarantine/
│   ├── reports/
│   └── kpis/
│
├── architecture/
│   └── aws_architecture.md
│
├── config/
│   └── config.yaml
│
├── tests/
├── dashboard.py
├── requirements.txt
└── README.md
```

---

## 15. Setup

Create a virtual environment:

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 16. Run Day 1

Place the Day 1 source files under:

```text
data/day1/
```

Then run:

```bash
python src/pipeline.py
```

The pipeline generates curated data, quarantine records, reports, and KPI outputs.

---

## 17. Run Day 2

Place the Day 2 files under:

```text
data/day2/
```

Then run:

```bash
python src/day2_incremental.py
```

The pipeline detects incremental changes and applies them without rebuilding the complete dataset.

---

## 18. AWS Production Architecture

The local MVP maps to the following AWS architecture:

```text
                 AWS
                  |
             Amazon S3
             Raw / Landing
                  |
                  v
          AWS Glue / PySpark
                  |
          +-------+-------+
          |               |
          v               v
     Cleansed Data    Quarantine
          |
          v
     Curated Layer
          |
          v
     Amazon Redshift
          |
          v
        KPI SQL
          |
          v
     Dashboard / BI
```

Supporting services:

- AWS Glue Data Quality for automated validation
- Step Functions for orchestration
- Lambda for event-driven pipeline triggering

The AWS architecture is a target production design; the submitted MVP runs locally using Python and Pandas.

See:

```text
architecture/aws_architecture.md
```

for the detailed AWS design.

---

## 19. Design Decisions

### Why Pandas for the MVP?

Pandas provides a fast implementation suitable for demonstrating the complete pipeline locally while preserving the same logical architecture used by a scalable cloud implementation.

### Why SCD Type 2?

SCD Type 2 preserves dimension history instead of overwriting previous business states.

### Why quarantine?

Invalid data should remain auditable rather than being silently removed.

### Why idempotency?

Repeated delivery of the same batch should not create duplicate business records or duplicate SCD versions.

### Why AWS?

AWS provides managed services covering storage, ETL, data quality, orchestration, analytics warehousing, and event-driven execution.

---

## 20. Demo Flow

Recommended hackathon demonstration:

1. Show the raw Day 1 data.
2. Run the Day 1 pipeline.
3. Show the data-quality scorecard.
4. Show quarantined records and reason codes.
5. Show the curated star schema.
6. Show the initial KPIs.
7. Introduce the Day 2 batch.
8. Show new and changed dimension records.
9. Demonstrate SCD Type 2 history.
10. Demonstrate a corrected transaction.
11. Show duplicate detection.
12. Show Day 2 KPI changes.
13. Rerun the same Day 2 batch to demonstrate idempotency.
14. Open the Streamlit dashboard.
15. Explain how the local pipeline maps to AWS production services.

---

## 21. Key Outcomes

The project demonstrates:

- Automated data-quality validation
- Auditable quarantine handling
- Star-schema modelling
- SCD Type 2 dimension management
- Incremental data processing
- Transaction correction handling
- Duplicate detection
- Idempotent batch processing
- KPI generation
- Interactive analytics
- AWS production architecture mapping

---

## 22. Future Enhancements

Potential production enhancements include:

- Deploying the ETL pipeline to AWS Glue
- Moving raw and curated datasets to Amazon S3
- Loading curated data into Amazon Redshift
- Adding AWS Glue Data Quality rules
- Adding Step Functions orchestration
- Adding Lambda-based event triggering
- Adding automated CI/CD
- Adding monitoring and alerting
- Adding role-based dashboard access
- Scaling processing using distributed PySpark jobs