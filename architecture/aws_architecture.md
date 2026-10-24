# AWS Production Architecture – Retail Bank Customer Analytics

## 1. Architecture Objective

The local Retail Bank Customer Analytics MVP is designed so that its processing logic can be migrated to AWS without changing the overall data flow.

The target AWS architecture provides:

- Scalable data ingestion
- Centralized raw-data storage
- Automated ETL processing
- Data-quality validation
- Quarantine of rejected records
- Curated dimensional and fact datasets
- Incremental Day 2 processing
- SCD Type 2 dimension management
- Transaction correction handling
- KPI generation
- Workflow orchestration
- Analytics and dashboard consumption

The AWS design is a **target production architecture**. The submitted MVP runs locally using Python and Pandas.

---

## 2. AWS Services

| Requirement | AWS Service | Purpose |
|---|---|---|
| Raw data storage | Amazon S3 | Store incoming CSV/JSON files |
| ETL / transformation | AWS Glue / PySpark | Scalable data processing |
| Data quality | AWS Glue Data Quality | Automated DQ rules and validation |
| Quarantine | Amazon S3 | Store rejected records and reason codes |
| Curated warehouse | Amazon Redshift | Analytics-ready star schema |
| Orchestration | AWS Step Functions | Coordinate pipeline stages |
| Event triggering | AWS Lambda | Trigger processing when new data arrives |
| KPI layer | Redshift SQL | Generate business KPIs |
| Visualization | Streamlit / BI | Present analytics to users |
| Version control | GitHub | Source-code management |

---

## 3. High-Level Architecture

```text
                         RETAIL BANK DATA SOURCES
                                   |
                                   v
                         +-------------------+
                         |    Amazon S3      |
                         |   Raw / Landing   |
                         +-------------------+
                                   |
                                   v
                         +-------------------+
                         |    AWS Glue       |
                         | ETL / PySpark     |
                         +-------------------+
                                   |
                     +-------------+-------------+
                     |                           |
                     v                           v
             +---------------+           +---------------+
             | Glue Data     |           |   Quarantine  |
             | Quality       |           |   S3 Bucket   |
             | Validation    |           | Rejected Data |
             +---------------+           +---------------+
                     |
                     v
             +-------------------+
             | Cleansed /        |
             | Curated Data      |
             |      S3           |
             +-------------------+
                     |
                     v
             +-------------------+
             | Amazon Redshift   |
             | Curated Star      |
             | Schema            |
             +-------------------+
                     |
                     v
             +-------------------+
             | KPI / SQL Layer   |
             +-------------------+
                     |
                     v
             +-------------------+
             | Dashboard / BI    |
             | Streamlit / BI    |
             +-------------------+


       Supporting orchestration:

       Amazon S3
           |
           v
       AWS Lambda
           |
           v
       AWS Step Functions
           |
           v
       AWS Glue Jobs
```

---

## 4. Data Flow

### Step 1 – Ingestion

Operational banking files are delivered to an Amazon S3 raw/landing location.

Example:

```text
s3://retail-bank-analytics/raw/day1/
s3://retail-bank-analytics/raw/day2/
```

Supported source formats include:

- CSV
- JSON

---

### Step 2 – ETL Processing

AWS Glue reads the raw data and performs:

- Schema normalization
- Type conversion
- Date normalization
- Identifier standardization
- Business-rule validation
- Duplicate detection
- Referential-integrity validation

The transformation logic follows the same logical rules implemented in the local Python MVP.

---

### Step 3 – Data Quality

AWS Glue Data Quality applies automated checks such as:

- Required fields are not null
- Transaction IDs are unique
- Amounts are valid
- Transaction dates are valid
- Transaction dates are not in the future
- Currency values are valid
- Customer references exist
- Product references exist
- Branch references exist

Records that fail validation are sent to the quarantine layer.

---

## 5. Quarantine Design

Invalid records are stored separately rather than silently discarded.

Example:

```text
s3://retail-bank-analytics/quarantine/

    customers/
    products/
    branches/
    transactions/
```

Each rejected transaction should retain a `reason_code`.

Example reason codes:

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

## 6. Curated Data Layer

Validated data is transformed into a star schema.

### Dimensions

```text
DIM_CUSTOMER
DIM_PRODUCT
DIM_BRANCH
```

### Fact

```text
FACT_TRANSACTION
```

The fact-table grain is:

> One row = one transaction.

Amazon Redshift is used as the target analytical warehouse.

---

## 7. SCD Type 2

Dimension changes are handled using Slowly Changing Dimension Type 2.

For example, when a customer's business attributes change:

```text
Existing Customer Version
          |
          | close old version
          v
New Customer Version
          |
          v
Current Record
```

The previous version remains available for historical analysis.

Typical SCD2 fields include:

```text
surrogate_key
business_key
effective_start_date
effective_end_date
is_current
```

This allows the system to preserve historical dimension states.

---

## 8. Day 2 Incremental Processing

Day 2 data is processed incrementally.

The pipeline identifies:

```text
New dimension records
Changed dimension records
Unchanged dimension records

New transactions
Corrected transactions
Duplicate transactions
Invalid transactions
```

The system does not require full reprocessing of all historical data.

Conceptually:

```text
Day 1 Curated State
        |
        +---------- Day 2 New Data
        |
        v
Incremental Processing
        |
        +---- New records
        +---- SCD2 changes
        +---- Transaction corrections
        +---- Duplicate handling
        +---- DQ quarantine
        |
        v
Updated Curated State
```

---

## 9. Transaction Correction Handling

Existing transactions are identified using `transaction_id`.

When a corrected version is received:

```text
Incoming Transaction
        |
        v
Find transaction_id
        |
   +----+----+
   |         |
 Found     Not Found
   |         |
   v         v
Update     Insert
Existing   New
Record     Transaction
```

This prevents corrected transactions from being counted twice.

---

## 10. Idempotency

The Day 2 pipeline is designed to be safely rerunnable.

A batch identifier or input-batch hash can be used to identify an already processed batch.

Conceptually:

```text
Incoming Batch
      |
      v
Calculate Batch Identifier
      |
      v
Already Processed?
   /          \
 Yes           No
 |             |
Stop       Process Batch
               |
               v
          Record Batch
```

If the exact same Day 2 batch is submitted again, the pipeline should not create:

- Duplicate transactions
- Duplicate SCD2 versions
- Duplicate correction counts

---

## 11. Orchestration

AWS Step Functions coordinates the pipeline stages.

Example workflow:

```text
Start
  |
  v
Validate Input
  |
  v
Run Glue ETL
  |
  v
Run Data Quality
  |
  +--------+
  |        |
  v        v
Pass     Reject
  |        |
  v        v
Curated  Quarantine
  |
  v
Load Redshift
  |
  v
Generate KPIs
  |
  v
Complete
```

AWS Lambda can trigger the Step Functions workflow when new files arrive in S3.

---

## 12. KPI Layer

The curated data is consumed by SQL-based KPI calculations.

Example KPI categories:

### Customer KPIs

- New customers
- Changed customers

### Product KPIs

- New products
- Changed products

### Branch KPIs

- New branches
- Changed branches

### Transaction KPIs

- New transactions
- Corrected transactions
- Total transaction count
- Total transaction amount
- Refund transaction count

Redshift SQL provides the analytical KPI layer.

---

## 13. Local MVP to AWS Mapping

| Local MVP | AWS Production Equivalent |
|---|---|
| Local `data/day1` | Amazon S3 Raw |
| Local `data/day2` | Amazon S3 Incremental Landing |
| `pipeline.py` | AWS Glue ETL Job |
| `day2_incremental.py` | AWS Glue Incremental Job |
| Pandas transformations | PySpark / Glue transformations |
| Local quarantine CSV | S3 Quarantine |
| Local curated CSV | S3 Curated + Redshift |
| SQL KPI files | Redshift SQL |
| Local orchestration | Step Functions |
| Manual trigger | Lambda / EventBridge |
| Streamlit dashboard | Streamlit / BI service |
| GitHub | GitHub / CI-CD |

---

## 14. Why AWS?

AWS was selected because it provides managed services covering the complete data-engineering lifecycle:

```text
Storage
   |
S3
   |
ETL
   |
Glue
   |
Data Quality
   |
Glue Data Quality
   |
Warehouse
   |
Redshift
   |
Orchestration
   |
Step Functions
   |
Triggering
   |
Lambda
```

This minimizes infrastructure management while providing a scalable architecture for growing transaction volumes.

---

## 15. Security and Governance

A production deployment should additionally use:

- IAM roles with least-privilege permissions
- S3 bucket policies
- Encryption at rest
- Encryption in transit
- Secrets Manager for credentials
- CloudWatch monitoring
- CloudTrail auditing
- VPC/network controls where required

Customer and transaction data should be protected throughout the pipeline.

---

## 16. Monitoring

Production monitoring can include:

- Glue job success/failure
- Number of records processed
- Number of records rejected
- Data-quality scores
- Processing duration
- Duplicate counts
- Transaction correction counts
- Redshift load status

CloudWatch can be used for operational monitoring and alerting.

---

## 17. Production Evolution

The submitted MVP demonstrates the complete processing logic locally.

A production deployment can evolve as follows:

```text
Local MVP
   |
   v
AWS S3
   |
   v
AWS Glue
   |
   v
Glue Data Quality
   |
   v
S3 Curated
   |
   v
Amazon Redshift
   |
   v
KPI / BI
```

The business rules, incremental-processing concepts, SCD2 logic, correction handling, quarantine strategy, and idempotency principles remain consistent during this migration.

---

## 18. Architecture Decision

The architecture separates:

1. Raw ingestion
2. Data-quality processing
3. Quarantine
4. Curated data
5. Analytical warehouse
6. KPI generation
7. Visualization

This separation improves:

- Auditability
- Maintainability
- Scalability
- Reprocessing capability
- Data-quality visibility
- Operational monitoring

The architecture is therefore suitable as a production-oriented evolution of the submitted local MVP.