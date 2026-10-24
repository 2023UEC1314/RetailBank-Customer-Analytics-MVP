import os
import json
import hashlib
import pandas as pd
import numpy as np

from pipeline import (
    read_any,
    find_file,
    normalize_cols,
    rename_aliases,
    standardize_customer,
    standardize_product,
    standardize_branch,
    standardize_transaction,
)

# ============================================================
# CONFIG
# ============================================================

OUT = "output/curated"
QUARANTINE = "output/quarantine"
REPORTS = "output/reports"
KPIS = "output/kpis"
DAY2 = "data/day2"

# Day 2 business date from the hackathon data
RUN_DATE = pd.Timestamp("2026-10-01")

# ============================================================
# DIRECTORIES
# ============================================================

def make_dirs():
    for folder in [OUT, QUARANTINE, REPORTS, KPIS]:
        os.makedirs(folder, exist_ok=True)


# ============================================================
# HELPERS
# ============================================================

def clean_value(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).strftime("%Y-%m-%d")

    if isinstance(value, float):
        if np.isnan(value):
            return None
        return round(value, 8)

    if isinstance(value, bool):
        return bool(value)

    return str(value).strip()


def values_equal(a, b):
    a = clean_value(a)
    b = clean_value(b)

    if a is None and b is None:
        return True

    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return np.isclose(float(a), float(b), equal_nan=True)

    return a == b


def normalize_date(value):
    if value is None:
        return None

    parsed = pd.to_datetime(value, errors="coerce")

    if pd.isna(parsed):
        return None

    return parsed.strftime("%Y-%m-%d")


def normalize_amount(value):
    if value is None:
        return None

    if isinstance(value, str):
        value = (
            value.replace("₹", "")
            .replace("$", "")
            .replace(",", "")
            .strip()
        )

    value = pd.to_numeric(value, errors="coerce")

    if pd.isna(value):
        return None

    return float(value)


def normalize_bool(value):
    if value is None:
        return 0

    if pd.isna(value):
        return 0

    return 1 if str(value).strip().lower() in {
        "true", "1", "yes", "y"
    } else 0


# ============================================================
# FILE BATCH FINGERPRINT
# ============================================================

def calculate_batch_hash():
    """
    Create a fingerprint of the Day 2 source files.

    This makes the same Day 2 batch completely idempotent.
    If the exact same batch is run again, no SCD2 versions
    or transaction corrections are created again.
    """

    files = [
        "customer_updates_day2.csv",
        "products_day2.json",
        "branches_day2.csv",
        "transactions_day2.csv",
    ]

    h = hashlib.sha256()

    for filename in files:
        path = os.path.join(DAY2, filename)

        if not os.path.exists(path):
            continue

        h.update(filename.encode("utf-8"))

        with open(path, "rb") as f:
            h.update(f.read())

    return h.hexdigest()


def marker_path():
    return os.path.join(REPORTS, "day2_batch_hash.txt")


def already_processed():
    path = marker_path()

    if not os.path.exists(path):
        return False

    try:
        with open(path, "r", encoding="utf-8") as f:
            old_hash = f.read().strip()

        return old_hash == calculate_batch_hash()

    except Exception:
        return False


def save_batch_hash():
    with open(marker_path(), "w", encoding="utf-8") as f:
        f.write(calculate_batch_hash())


# ============================================================
# SCD HELPERS
# ============================================================

def ensure_scd_columns(df, surrogate_key):
    df = df.copy()

    if surrogate_key not in df.columns:
        df[surrogate_key] = range(1, len(df) + 1)

    if "effective_from" not in df.columns:
        df["effective_from"] = RUN_DATE

    if "effective_to" not in df.columns:
        df["effective_to"] = pd.NaT

    if "is_current" not in df.columns:
        df["is_current"] = 1

    df["effective_from"] = pd.to_datetime(
        df["effective_from"],
        errors="coerce"
    )

    df["effective_to"] = pd.to_datetime(
        df["effective_to"],
        errors="coerce"
    )

    df["is_current"] = (
        pd.to_numeric(
            df["is_current"],
            errors="coerce"
        )
        .fillna(1)
        .astype(int)
    )

    df[surrogate_key] = pd.to_numeric(
        df[surrogate_key],
        errors="coerce"
    )

    if len(df):
        max_key = int(df[surrogate_key].max())
    else:
        max_key = 0

    missing_keys = df[surrogate_key].isna()

    if missing_keys.any():
        df.loc[missing_keys, surrogate_key] = range(
            max_key + 1,
            max_key + 1 + int(missing_keys.sum())
        )

    df[surrogate_key] = df[surrogate_key].astype(int)

    return df


def current_rows(df, business_key):
    if df.empty:
        return df.copy()

    return df[
        df["is_current"] == 1
    ].copy()


def get_current_record(df, business_key, key):
    if df.empty or pd.isna(key):
        return None

    key = str(key).strip()

    current = current_rows(df, business_key)

    matches = current[
        current[business_key]
        .astype(str)
        .str.strip()
        == key
    ]

    if matches.empty:
        return None

    return matches.iloc[0]


def get_current_surrogate(df, business_key, key, surrogate_key):
    row = get_current_record(
        df,
        business_key,
        key
    )

    if row is None:
        return None

    return int(row[surrogate_key])


# ============================================================
# GENERIC SCD2
# ============================================================

def scd2_update(
    existing,
    incoming,
    business_key,
    surrogate_key,
    tracked_columns
):
    """
    Idempotent SCD Type 2 update.

    Important:
    - Same business key + same tracked values => unchanged.
    - New business key => new row.
    - Changed business key => close old + create new version.
    - Never creates another version for an already-applied
      Day 2 record.
    """

    existing = ensure_scd_columns(
        existing.copy(),
        surrogate_key
    )

    incoming = incoming.copy()

    if incoming.empty:
        return existing, {
            "new": 0,
            "changed": 0,
            "unchanged": 0
        }

    if "reason_code" in incoming.columns:
        incoming = incoming.drop(
            columns=["reason_code"]
        )

    incoming = incoming.drop_duplicates(
        subset=[business_key],
        keep="last"
    )

    existing = existing.astype(object)

    max_key = (
        int(existing[surrogate_key].max())
        if not existing.empty
        else 0
    )

    new_count = 0
    changed_count = 0
    unchanged_count = 0

    for _, row in incoming.iterrows():

        key = row.get(business_key)

        if pd.isna(key):
            continue

        key = str(key).strip()

        current = current_rows(
            existing,
            business_key
        )

        matches = current[
            current[business_key]
            .astype(str)
            .str.strip()
            == key
        ]

        # ----------------------------------------------------
        # NEW RECORD
        # ----------------------------------------------------

        if matches.empty:

            max_key += 1

            new_record = row.to_dict()

            new_record[surrogate_key] = max_key
            new_record["effective_from"] = RUN_DATE
            new_record["effective_to"] = pd.NaT
            new_record["is_current"] = 1

            existing = pd.concat(
                [
                    existing,
                    pd.DataFrame([new_record])
                ],
                ignore_index=True
            )

            new_count += 1

            continue

        # ----------------------------------------------------
        # EXISTING RECORD
        # ----------------------------------------------------

        idx = matches.index[0]

        changed = False

        for col in tracked_columns:

            if col not in existing.columns:
                continue

            old_value = existing.loc[idx, col]
            new_value = row.get(col)

            if not values_equal(
                old_value,
                new_value
            ):
                changed = True
                break

        # ----------------------------------------------------
        # UNCHANGED
        # ----------------------------------------------------

        if not changed:

            unchanged_count += 1

            continue

        # ----------------------------------------------------
        # IMPORTANT SCD2 DATE FIX
        # ----------------------------------------------------

        old_effective_from = pd.to_datetime(
            existing.loc[idx, "effective_from"],
            errors="coerce"
        )

        # Never create:
        # effective_to < effective_from
        #
        # If Day 1 was generated after the synthetic Day 2
        # business date, use the existing effective_from as
        # the boundary rather than creating an invalid interval.

        close_date = RUN_DATE

        if (
            pd.notna(old_effective_from)
            and close_date < old_effective_from
        ):
            close_date = old_effective_from

        existing.loc[
            idx,
            "effective_to"
        ] = close_date

        existing.loc[
            idx,
            "is_current"
        ] = 0

        # ----------------------------------------------------
        # CREATE NEW VERSION
        # ----------------------------------------------------

        max_key += 1

        new_record = row.to_dict()

        new_record[surrogate_key] = max_key
        new_record["effective_from"] = close_date
        new_record["effective_to"] = pd.NaT
        new_record["is_current"] = 1

        existing = pd.concat(
            [
                existing,
                pd.DataFrame([new_record])
            ],
            ignore_index=True
        )

        changed_count += 1

    existing = ensure_scd_columns(
        existing,
        surrogate_key
    )

    return existing, {
        "new": new_count,
        "changed": changed_count,
        "unchanged": unchanged_count
    }


# ============================================================
# VALIDATION
# ============================================================

def add_reason(reasons, bad, mask, code):
    mask = mask.fillna(False)

    for idx in reasons.index[mask]:
        if reasons.loc[idx]:
            reasons.loc[idx] += ";" + code
        else:
            reasons.loc[idx] = code

    bad |= mask

    return bad, reasons


def validate_customers(df):
    df = df.copy()

    bad = pd.Series(
        False,
        index=df.index
    )

    reasons = pd.Series(
        "",
        index=df.index,
        dtype="object"
    )

    if "customer_id" in df.columns:

        bad, reasons = add_reason(
            reasons,
            bad,
            df["customer_id"].isna()
            |
            (
                df["customer_id"]
                .astype(str)
                .str.strip()
                == ""
            ),
            "MISSING_CUSTOMER_ID"
        )

    if "email" in df.columns:

        email = (
            df["email"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        bad, reasons = add_reason(
            reasons,
            bad,
            email.eq(""),
            "MISSING_EMAIL"
        )

        bad, reasons = add_reason(
            reasons,
            bad,
            email.ne("")
            &
            (
                ~email.str.contains(
                    "@",
                    regex=False
                )
                |
                email.str.contains(
                    "@@",
                    regex=False
                )
            ),
            "INVALID_EMAIL"
        )

    if "registration_date" in df.columns:

        parsed = pd.to_datetime(
            df["registration_date"],
            errors="coerce"
        )

        bad, reasons = add_reason(
            reasons,
            bad,
            parsed.isna(),
            "INVALID_REGISTRATION_DATE"
        )

    if "dob" in df.columns:

        original = (
            df["dob"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        parsed = pd.to_datetime(
            df["dob"],
            errors="coerce"
        )

        bad, reasons = add_reason(
            reasons,
            bad,
            original.ne("")
            &
            parsed.isna(),
            "INVALID_DOB"
        )

    df["reason_code"] = reasons

    return (
        df[~bad].copy(),
        df[bad].copy()
    )


def validate_products(df):
    df = df.copy()

    bad = pd.Series(
        False,
        index=df.index
    )

    reasons = pd.Series(
        "",
        index=df.index,
        dtype="object"
    )

    if "product_id" in df.columns:

        bad, reasons = add_reason(
            reasons,
            bad,
            df["product_id"].isna()
            |
            (
                df["product_id"]
                .astype(str)
                .str.strip()
                == ""
            ),
            "MISSING_PRODUCT_ID"
        )

    if "product_name" in df.columns:

        bad, reasons = add_reason(
            reasons,
            bad,
            df["product_name"].isna()
            |
            (
                df["product_name"]
                .astype(str)
                .str.strip()
                == ""
            ),
            "MISSING_PRODUCT_NAME"
        )

    if "price" in df.columns:

        price = pd.to_numeric(
            df["price"],
            errors="coerce"
        )

        bad, reasons = add_reason(
            reasons,
            bad,
            price.isna(),
            "INVALID_PRICE"
        )

        bad, reasons = add_reason(
            reasons,
            bad,
            price.notna()
            &
            (price < 0),
            "NEGATIVE_PRICE"
        )

    df["reason_code"] = reasons

    return (
        df[~bad].copy(),
        df[bad].copy()
    )


def validate_branches(df):
    df = df.copy()

    bad = pd.Series(
        False,
        index=df.index
    )

    reasons = pd.Series(
        "",
        index=df.index,
        dtype="object"
    )

    if "branch_id" in df.columns:

        bad, reasons = add_reason(
            reasons,
            bad,
            df["branch_id"].isna()
            |
            (
                df["branch_id"]
                .astype(str)
                .str.strip()
                == ""
            ),
            "MISSING_BRANCH_ID"
        )

    if "branch_name" in df.columns:

        bad, reasons = add_reason(
            reasons,
            bad,
            df["branch_name"].isna()
            |
            (
                df["branch_name"]
                .astype(str)
                .str.strip()
                == ""
            ),
            "MISSING_BRANCH_NAME"
        )

    if "opened_date" in df.columns:

        original = (
            df["opened_date"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        parsed = pd.to_datetime(
            df["opened_date"],
            errors="coerce"
        )

        bad, reasons = add_reason(
            reasons,
            bad,
            original.ne("")
            &
            parsed.isna(),
            "INVALID_OPENED_DATE"
        )

    df["reason_code"] = reasons

    return (
        df[~bad].copy(),
        df[bad].copy()
    )


# ============================================================
# TRANSACTIONS
# ============================================================

def normalize_transaction_dates(df):
    df = df.copy()

    if "transaction_date" in df.columns:

        df["transaction_date"] = pd.to_datetime(
            df["transaction_date"],
            errors="coerce"
        )

    else:

        df["transaction_date"] = pd.NaT

    if "amount" in df.columns:

        df["amount"] = pd.to_numeric(
            df["amount"],
            errors="coerce"
        )

    return df


def validate_transactions(
    df,
    customers=None,
    products=None,
    branches=None
):
    df = normalize_transaction_dates(df)

    bad = pd.Series(
        False,
        index=df.index
    )

    reasons = pd.Series(
        "",
        index=df.index,
        dtype="object"
    )

    if "transaction_id" in df.columns:
        bad, reasons = add_reason(
            reasons,
            bad,
            df["transaction_id"].isna()
            |
            (
                df["transaction_id"]
                .astype(str)
                .str.strip()
                == ""
            ),
            "MISSING_TRANSACTION_ID"
        )

    if "account_id" in df.columns:
        bad, reasons = add_reason(
            reasons,
            bad,
            df["account_id"].isna()
            |
            (
                df["account_id"]
                .astype(str)
                .str.strip()
                == ""
            ),
            "MISSING_ACCOUNT_ID"
        )

        if "customer_id" in df.columns:
         bad, reasons = add_reason(
            reasons,
            bad,
            df["customer_id"].isna()
            |
            (
                df["customer_id"]
                .astype(str)
                .str.strip()
                == ""
            ),
            "UNRESOLVED_CUSTOMER_REFERENCE"
        )    

    if "product_id" in df.columns:
        bad, reasons = add_reason(
            reasons,
            bad,
            df["product_id"].isna()
            |
            (
                df["product_id"]
                .astype(str)
                .str.strip()
                == ""
            ),
            "MISSING_PRODUCT_ID"
        )

    if "branch_id" in df.columns:
        bad, reasons = add_reason(
            reasons,
            bad,
            df["branch_id"].isna()
            |
            (
                df["branch_id"]
                .astype(str)
                .str.strip()
                == ""
            ),
            "MISSING_BRANCH_ID"
        )

    if "amount" in df.columns:

        amount = pd.to_numeric(
            df["amount"],
            errors="coerce"
        )

        bad, reasons = add_reason(
            reasons,
            bad,
            amount.isna(),
            "INVALID_AMOUNT"
        )

        bad, reasons = add_reason(
            reasons,
            bad,
            amount < 0,
            "NEGATIVE_AMOUNT"
        )

    bad, reasons = add_reason(
        reasons,
        bad,
        df["transaction_date"].isna(),
        "INVALID_TRANSACTION_DATE"
    )

    # ---------------------------------------------------------
    # Referential integrity checks
    # ---------------------------------------------------------

    if customers is not None and "customer_id" in df.columns:

        valid_customers = set(
            customers["customer_id"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        missing_customer = (
            df["customer_id"]
            .astype(str)
            .str.strip()
            .isin(valid_customers)
            == False
        )

        missing_customer &= df["customer_id"].notna()

        bad, reasons = add_reason(
            reasons,
            bad,
            missing_customer,
            "ORPHAN_CUSTOMER_ID"
        )

    if products is not None and "product_id" in df.columns:

        valid_products = set(
            products["product_id"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        missing_product = (
            df["product_id"]
            .astype(str)
            .str.strip()
            .isin(valid_products)
            == False
        )

        missing_product &= df["product_id"].notna()

        bad, reasons = add_reason(
            reasons,
            bad,
            missing_product,
            "ORPHAN_PRODUCT_ID"
        )

    if branches is not None and "branch_id" in df.columns:

        valid_branches = set(
            branches["branch_id"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        missing_branch = (
            df["branch_id"]
            .astype(str)
            .str.strip()
            .isin(valid_branches)
            == False
        )

        missing_branch &= df["branch_id"].notna()

        bad, reasons = add_reason(
            reasons,
            bad,
            missing_branch,
            "ORPHAN_BRANCH_ID"
        )

    df["reason_code"] = reasons

    return (
        df[~bad].copy(),
        df[bad].copy()
    )


def map_account_to_customer(
    transactions,
    customers
):
    transactions = transactions.copy()

    if "customer_id" in transactions.columns:
        return transactions

    if "account_id" not in transactions.columns:
        transactions["customer_id"] = None
        return transactions

    current = current_rows(
        customers,
        "customer_id"
    )

    mapping = (
        current[
            ["account_id", "customer_id"]
        ]
        .drop_duplicates(
            "account_id"
        )
    )

    return transactions.merge(
        mapping,
        on="account_id",
        how="left"
    )


def deduplicate_transactions(df):
    """
    Exact duplicates:
        remove duplicates.

    Conflicting IDs:
        retain the last source version.

    Returns:
        cleaned_df,
        exact_duplicate_count,
        conflicting_version_count
    """

    if df.empty:
        return df, 0, 0

    df = df.copy()

    before = len(df)

    df = df.drop_duplicates(
        keep="last"
    )

    exact_duplicates = before - len(df)

    corrections = 0

    if "transaction_id" not in df.columns:
        return (
            df,
            exact_duplicates,
            corrections
        )

    duplicate_ids = (
        df["transaction_id"]
        .value_counts()
    )

    duplicate_ids = duplicate_ids[
        duplicate_ids > 1
    ].index.tolist()

    if duplicate_ids:

        keep_rows = []

        for tid in duplicate_ids:

            group = df[
                df["transaction_id"]
                == tid
            ].copy()

            if len(
                group.drop_duplicates()
            ) > 1:

                corrections += (
                    len(group) - 1
                )

            keep_rows.append(
                group.iloc[-1]
            )

        df = df[
            ~df["transaction_id"].isin(
                duplicate_ids
            )
        ]

        if keep_rows:

            df = pd.concat(
                [
                    df,
                    pd.DataFrame(keep_rows)
                ],
                ignore_index=True
            )

    return (
        df,
        exact_duplicates,
        corrections
    )


# ============================================================
# FACT UPSERT
# ============================================================

def normalize_fact_value(
    col,
    value
):
    if col == "transaction_date":
        return normalize_date(value)

    if col == "amount":
        return normalize_amount(value)

    if col in {
        "customer_key",
        "product_key",
        "branch_key",
        "transaction_key"
    }:

        if value is None or pd.isna(value):
            return None

        parsed = pd.to_numeric(
            value,
            errors="coerce"
        )

        if pd.isna(parsed):
            return None

        return int(parsed)

    if col == "is_refund":
        return normalize_bool(value)

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    return value


def rows_differ(
    old_row,
    new_row,
    fact_columns,
    ignored=None
):
    ignored = ignored or set()

    for col in new_row.index:

        if col in ignored:
            continue

        if col not in fact_columns:
            continue

        old_value = normalize_fact_value(
            col,
            old_row.get(col)
        )

        new_value = normalize_fact_value(
            col,
            new_row.get(col)
        )

        if not values_equal(
            old_value,
            new_value
        ):
            return True

    return False


def get_key(
    dimension,
    business_key,
    business_value,
    surrogate_key
):
    return get_current_surrogate(
        dimension,
        business_key,
        business_value,
        surrogate_key
    )


def upsert_transactions(
    fact,
    incoming,
    customers,
    products,
    branches
):
    fact = fact.copy().astype(object)

    if incoming.empty:
        return fact, 0, 0

    if "transaction_key" not in fact.columns:
        fact["transaction_key"] = range(
            1,
            len(fact) + 1
        )

    fact["transaction_key"] = pd.to_numeric(
        fact["transaction_key"],
        errors="coerce"
    )

    max_key = (
        int(fact["transaction_key"].max())
        if fact["transaction_key"].notna().any()
        else 0
    )

    inserted = 0
    corrected = 0

    existing_ids = set(
        fact["transaction_id"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    for _, row in incoming.iterrows():

        tid = str(
            row.get(
                "transaction_id",
                ""
            )
        ).strip()

        if not tid:
            continue

        customer_key = get_key(
            customers,
            "customer_id",
            row.get("customer_id"),
            "customer_key"
        )

        product_key = get_key(
            products,
            "product_id",
            row.get("product_id"),
            "product_key"
        )

        branch_key = get_key(
            branches,
            "branch_id",
            row.get("branch_id"),
            "branch_key"
        )

        # ----------------------------------------------------
        # EXISTING TRANSACTION
        # ----------------------------------------------------

        if tid in existing_ids:

            matches = fact[
                fact["transaction_id"]
                .astype(str)
                .str.strip()
                == tid
            ]

            if matches.empty:
                continue

            idx = matches.index[0]

            comparison = row.copy()

            comparison["customer_key"] = (
                customer_key
            )

            comparison["product_key"] = (
                product_key
            )

            comparison["branch_key"] = (
                branch_key
            )

            changed = rows_differ(
                fact.loc[idx],
                comparison,
                fact.columns,
                ignored={"transaction_key"}
            )

            if not changed:
                # Already applied.
                continue

            # Apply correction.
            for col in row.index:

                if col not in fact.columns:
                    continue

                fact.loc[idx, col] = (
                    normalize_fact_value(
                        col,
                        row[col]
                    )
                )

            fact.loc[
                idx,
                "customer_key"
            ] = customer_key

            fact.loc[
                idx,
                "product_key"
            ] = product_key

            fact.loc[
                idx,
                "branch_key"
            ] = branch_key

            corrected += 1

            continue

        # ----------------------------------------------------
        # NEW TRANSACTION
        # ----------------------------------------------------

        max_key += 1

        new_row = {
            col: None
            for col in fact.columns
        }

        for col in row.index:

            if col in new_row:

                new_row[col] = (
                    normalize_fact_value(
                        col,
                        row[col]
                    )
                )

        new_row["transaction_id"] = tid
        new_row["transaction_key"] = max_key

        new_row["customer_key"] = customer_key
        new_row["product_key"] = product_key
        new_row["branch_key"] = branch_key

        fact = pd.concat(
            [
                fact,
                pd.DataFrame(
                    [new_row],
                    columns=fact.columns
                )
            ],
            ignore_index=True
        )

        existing_ids.add(tid)

        inserted += 1

    return (
        fact,
        inserted,
        corrected
    )


# ============================================================
# KPI 11
# ============================================================

def calculate_kpi_11(
    customer_stats,
    product_stats,
    branch_stats
):
    return pd.DataFrame([
        {
            "metric": "new_customers",
            "value": customer_stats["new"]
        },
        {
            "metric": "changed_customers",
            "value": customer_stats["changed"]
        },
        {
            "metric": "new_products",
            "value": product_stats["new"]
        },
        {
            "metric": "changed_products",
            "value": product_stats["changed"]
        },
        {
            "metric": "new_branches",
            "value": branch_stats["new"]
        },
        {
            "metric": "changed_branches",
            "value": branch_stats["changed"]
        }
    ])


# ============================================================
# KPI 12
# ============================================================

def calculate_kpi_12(
    inserted,
    corrected
):
    return pd.DataFrame([
        {
            "metric": "new_transactions",
            "value": inserted
        },
        {
            "metric": "corrected_transactions",
            "value": corrected
        }
    ])


# ============================================================
# KPI 13
# ============================================================

def calculate_kpi_13(fact):

    if fact.empty:
        return pd.DataFrame([
            {
                "metric":
                "total_transaction_count",
                "value": 0
            },
            {
                "metric":
                "total_transaction_amount",
                "value": 0
            },
            {
                "metric":
                "refund_transaction_count",
                "value": 0
            }
        ])

    amount = pd.to_numeric(
        fact["amount"],
        errors="coerce"
    ).fillna(0)

    refund_count = (
        fact["is_refund"]
        .astype(str)
        .str.lower()
        .isin([
            "true",
            "1",
            "yes"
        ])
        .sum()
    )

    return pd.DataFrame([
        {
            "metric":
            "total_transaction_count",
            "value": len(fact)
        },
        {
            "metric":
            "total_transaction_amount",
            "value": amount.sum()
        },
        {
            "metric":
            "refund_transaction_count",
            "value": int(refund_count)
        }
    ])


# ============================================================
# SAVE
# ============================================================

def save_dimension(
    df,
    filename
):
    df = df.copy()

    df["effective_from"] = (
        pd.to_datetime(
            df["effective_from"],
            errors="coerce"
        )
        .dt.strftime("%Y-%m-%d")
    )

    df["effective_to"] = (
        pd.to_datetime(
            df["effective_to"],
            errors="coerce"
        )
        .dt.strftime("%Y-%m-%d")
    )

    df.to_csv(
        os.path.join(
            OUT,
            filename
        ),
        index=False
    )


def normalize_final_fact(fact):

    fact = fact.copy()

    if "transaction_date" in fact.columns:

        fact["transaction_date"] = (
            pd.to_datetime(
                fact["transaction_date"],
                errors="coerce"
            )
            .dt.strftime("%Y-%m-%d")
        )

    if "amount" in fact.columns:

        fact["amount"] = pd.to_numeric(
            fact["amount"],
            errors="coerce"
        )

    for col in [
        "transaction_key",
        "customer_key",
        "product_key",
        "branch_key"
    ]:

        if col in fact.columns:

            fact[col] = (
                pd.to_numeric(
                    fact[col],
                    errors="coerce"
                )
                .astype("Int64")
            )

    if "is_refund" in fact.columns:

        fact["is_refund"] = (
            fact["is_refund"]
            .astype(str)
            .str.lower()
            .isin([
                "true",
                "1",
                "yes",
                "y"
            ])
            .astype(int)
        )

    return fact


# ============================================================
# MAIN
# ============================================================

def run_day2():

    print("=" * 70)
    print("RETAILBANK - DAY 2 INCREMENTAL PIPELINE")
    print("=" * 70)

    make_dirs()

    # --------------------------------------------------------
    # LOCATE FILES
    # --------------------------------------------------------

    customer_path = find_file(
        DAY2,
        ["customer_updates_day2.csv"]
    )

    product_path = find_file(
        DAY2,
        [
            "products_day2.json",
            "products_day2.csv"
        ]
    )

    branch_path = find_file(
        DAY2,
        ["branches_day2.csv"]
    )

    transaction_path = find_file(
        DAY2,
        ["transactions_day2.csv"]
    )

    print("\nDay 2 input files:")
    print("Customer updates:", customer_path)
    print("Product updates :", product_path)
    print("Branch updates  :", branch_path)
    print("Transaction updates:", transaction_path)

    # --------------------------------------------------------
    # LOAD CURATED DATA
    # --------------------------------------------------------

    print("\nLoading Day 1 curated data...")

    c = pd.read_csv(
        os.path.join(
            OUT,
            "dim_customer.csv"
        )
    )

    p = pd.read_csv(
        os.path.join(
            OUT,
            "dim_product.csv"
        )
    )

    b = pd.read_csv(
        os.path.join(
            OUT,
            "dim_branch.csv"
        )
    )

    f = pd.read_csv(
        os.path.join(
            OUT,
            "fact_transaction.csv"
        )
    )

    c = ensure_scd_columns(
        c,
        "customer_key"
    )

    p = ensure_scd_columns(
        p,
        "product_key"
    )

    b = ensure_scd_columns(
        b,
        "branch_key"
    )

    print("Existing customers :", len(c))
    print("Existing products  :", len(p))
    print("Existing branches  :", len(b))
    print("Existing facts     :", len(f))

    # --------------------------------------------------------
    # IDEMPOTENCY CHECK
    # --------------------------------------------------------

    same_batch = already_processed()

    if same_batch:

        print()
        print("=" * 70)
        print("DAY 2 BATCH ALREADY PROCESSED")
        print("=" * 70)
        print("This exact Day 2 input batch was already applied.")
        print("No duplicate SCD2 versions will be created.")
        print("No transaction corrections will be re-counted.")
        print()

        # Write zero-change KPIs.

        zero_kpi11 = pd.DataFrame([
            ["new_customers", 0],
            ["changed_customers", 0],
            ["new_products", 0],
            ["changed_products", 0],
            ["new_branches", 0],
            ["changed_branches", 0],
        ], columns=["metric", "value"])

        zero_kpi12 = pd.DataFrame([
            ["new_transactions", 0],
            ["corrected_transactions", 0],
        ], columns=["metric", "value"])

        zero_kpi11.to_csv(
            os.path.join(
                KPIS,
                "kpi_11.csv"
            ),
            index=False
        )

        zero_kpi12.to_csv(
            os.path.join(
                KPIS,
                "kpi_12.csv"
            ),
            index=False
        )

        kpi13 = calculate_kpi_13(f)

        kpi13.to_csv(
            os.path.join(
                KPIS,
                "kpi_13.csv"
            ),
            index=False
        )

        print(
            f"Customers : {len(c)}"
        )
        print(
            f"Products  : {len(p)}"
        )
        print(
            f"Branches  : {len(b)}"
        )
        print(
            f"Facts     : {len(f)}"
        )

        return

    # ========================================================
    # CUSTOMER UPDATES
    # ========================================================

    customer_stats = {
        "new": 0,
        "changed": 0,
        "unchanged": 0
    }

    print("\n[1/4] Processing customers...")

    raw = read_any(customer_path)
    raw = normalize_cols(raw)

    incoming = standardize_customer(raw)

    passed, rejected = validate_customers(
        incoming
    )

    if not rejected.empty:

        rejected.to_csv(
            os.path.join(
                QUARANTINE,
                "customers_day2.csv"
            ),
            index=False
        )

        print(
            f"  Quarantined {len(rejected)} "
            "customers record(s)"
        )

    print("  Received :", len(incoming))
    print("  Passed   :", len(passed))
    print("  Rejected :", len(rejected))

    tracked = [
        "name",
        "email",
        "phone",
        "gender",
        "dob",
        "address",
        "kyc_status",
        "account_id",
        "registration_date"
    ]

    tracked = [
        col
        for col in tracked
        if col in passed.columns
        and col in c.columns
    ]

    c, customer_stats = scd2_update(
        c,
        passed,
        "customer_id",
        "customer_key",
        tracked
    )

    print("  New      :", customer_stats["new"])
    print("  Changed  :", customer_stats["changed"])
    print("  Unchanged:", customer_stats["unchanged"])

    # ========================================================
    # PRODUCT UPDATES
    # ========================================================

    product_stats = {
        "new": 0,
        "changed": 0,
        "unchanged": 0
    }

    print("\n[2/4] Processing products...")

    raw = read_any(product_path)
    raw = normalize_cols(raw)

    incoming = standardize_product(raw)

    passed, rejected = validate_products(
        incoming
    )

    if not rejected.empty:

        rejected.to_csv(
            os.path.join(
                QUARANTINE,
                "products_day2.csv"
            ),
            index=False
        )

        print(
            f"  Quarantined {len(rejected)} "
            "products record(s)"
        )

    print("  Received :", len(incoming))
    print("  Passed   :", len(passed))
    print("  Rejected :", len(rejected))

    tracked = [
        "product_name",
        "category",
        "price",
        "is_active"
    ]

    tracked = [
        col
        for col in tracked
        if col in passed.columns
        and col in p.columns
    ]

    p, product_stats = scd2_update(
        p,
        passed,
        "product_id",
        "product_key",
        tracked
    )

    print("  New      :", product_stats["new"])
    print("  Changed  :", product_stats["changed"])
    print("  Unchanged:", product_stats["unchanged"])

    # ========================================================
    # BRANCH UPDATES
    # ========================================================

    branch_stats = {
        "new": 0,
        "changed": 0,
        "unchanged": 0
    }

    print("\n[3/4] Processing branches...")

    raw = read_any(branch_path)
    raw = normalize_cols(raw)

    incoming = standardize_branch(raw)

    passed, rejected = validate_branches(
        incoming
    )

    if not rejected.empty:

        rejected.to_csv(
            os.path.join(
                QUARANTINE,
                "branches_day2.csv"
            ),
            index=False
        )

    print("  Received :", len(incoming))
    print("  Passed   :", len(passed))
    print("  Rejected :", len(rejected))

    # IMPORTANT:
    # These are the actual names in the standardized data.
    # phone is later compatible with contact_number only if
    # the existing dimension uses phone. If the Day 1 dimension
    # uses contact_number, include that mapping below.

    if "phone" not in passed.columns:
        if "contact_number" in passed.columns:
            passed["phone"] = passed["contact_number"]

    if "phone" not in b.columns:
        if "contact_number" in b.columns:
            b["phone"] = b["contact_number"]

    tracked = [
        "branch_name",
        "location",
        "manager",
        "opened_date",
        "region",
        "branch_type",
        "phone",
        "contact_number"
    ]

    tracked = [
        col
        for col in tracked
        if col in passed.columns
        and col in b.columns
    ]

    b, branch_stats = scd2_update(
        b,
        passed,
        "branch_id",
        "branch_key",
        tracked
    )

    print("  New      :", branch_stats["new"])
    print("  Changed  :", branch_stats["changed"])
    print("  Unchanged:", branch_stats["unchanged"])

    # ========================================================
    # TRANSACTIONS
    # ========================================================

    print("\n[4/4] Processing transactions...")

    raw = read_any(transaction_path)
    raw = normalize_cols(raw)

    incoming = standardize_transaction(raw)

    incoming = map_account_to_customer(
        incoming,
        c
    )

    passed, rejected = validate_transactions(
    incoming,
    customers=c,
    products=p,
    branches=b
   )

    if not rejected.empty:

        rejected.to_csv(
            os.path.join(
                QUARANTINE,
                "transactions_day2.csv"
            ),
            index=False
        )

        print(
            f"  Quarantined {len(rejected)} "
            "transactions record(s)"
        )

    print("  Received :", len(incoming))
    print("  Passed   :", len(passed))
    print("  Rejected :", len(rejected))

    passed, duplicate_count, correction_versions = (
        deduplicate_transactions(
            passed
        )
    )

    print(
        "  Exact duplicates removed:",
        duplicate_count
    )

    print(
        "  Correction versions detected:",
        correction_versions
    )

    f, inserted, corrected = upsert_transactions(
        f,
        passed,
        c,
        p,
        b
    )

    print(
        "  New transactions :",
        inserted
    )

    print(
        "  Corrected        :",
        corrected
    )

    # ========================================================
    # FINAL SAFETY CHECK
    # ========================================================

    f = normalize_final_fact(f)

    # Remove accidental duplicate transaction IDs.
    # Keep latest row.
    if "transaction_id" in f.columns:

        f = f.drop_duplicates(
            subset=["transaction_id"],
            keep="last"
        ).reset_index(drop=True)

    # Re-number transaction keys after final deduplication.
    f["transaction_key"] = range(
        1,
        len(f) + 1
    )

    # ========================================================
    # SAVE CURATED DATA
    # ========================================================

    save_dimension(
        c,
        "dim_customer.csv"
    )

    save_dimension(
        p,
        "dim_product.csv"
    )

    save_dimension(
        b,
        "dim_branch.csv"
    )

    f.to_csv(
        os.path.join(
            OUT,
            "fact_transaction.csv"
        ),
        index=False
    )

    # ========================================================
    # KPI 11
    # ========================================================

    kpi11 = calculate_kpi_11(
        customer_stats,
        product_stats,
        branch_stats
    )

    kpi11.to_csv(
        os.path.join(
            KPIS,
            "kpi_11.csv"
        ),
        index=False
    )

    # ========================================================
    # KPI 12
    # ========================================================

    kpi12 = calculate_kpi_12(
        inserted,
        corrected
    )

    kpi12.to_csv(
        os.path.join(
            KPIS,
            "kpi_12.csv"
        ),
        index=False
    )

    # ========================================================
    # KPI 13
    # ========================================================

    kpi13 = calculate_kpi_13(
        f
    )

    kpi13.to_csv(
        os.path.join(
            KPIS,
            "kpi_13.csv"
        ),
        index=False
    )

    # ========================================================
    # DAY 2 SUMMARY
    # ========================================================

    summary = pd.DataFrame([
        {
            "entity": "customers",
            "new": customer_stats["new"],
            "changed": customer_stats["changed"],
            "unchanged": customer_stats["unchanged"]
        },
        {
            "entity": "products",
            "new": product_stats["new"],
            "changed": product_stats["changed"],
            "unchanged": product_stats["unchanged"]
        },
        {
            "entity": "branches",
            "new": branch_stats["new"],
            "changed": branch_stats["changed"],
            "unchanged": branch_stats["unchanged"]
        },
        {
            "entity": "transactions",
            "new": inserted,
            "changed": corrected,
            "unchanged": duplicate_count
        }
    ])

    summary.to_csv(
        os.path.join(
            REPORTS,
            "day2_summary.csv"
        ),
        index=False
    )

    # Save batch fingerprint ONLY after successful processing.
    save_batch_hash()

    # ========================================================
    # FINAL OUTPUT
    # ========================================================

    print()
    print("=" * 70)
    print("DAY 2 PIPELINE COMPLETE")
    print("=" * 70)

    print(
        f"Customers : {len(c)} rows"
    )

    print(
        f"Products  : {len(p)} rows"
    )

    print(
        f"Branches  : {len(b)} rows"
    )

    print(
        f"Facts     : {len(f)} rows"
    )

    print()
    print("Day 2 changes:")

    print(
        "  New customers       :",
        customer_stats["new"]
    )

    print(
        "  Changed customers   :",
        customer_stats["changed"]
    )

    print(
        "  New products        :",
        product_stats["new"]
    )

    print(
        "  Changed products    :",
        product_stats["changed"]
    )

    print(
        "  New branches        :",
        branch_stats["new"]
    )

    print(
        "  Changed branches    :",
        branch_stats["changed"]
    )

    print(
        "  New transactions    :",
        inserted
    )

    print(
        "  Corrected           :",
        corrected
    )

    print(
        "  Duplicate rows      :",
        duplicate_count
    )

    print(
        "  Rejected            :",
        len(rejected)
    )

    print()
    print("Generated files:")
    print("  output/curated/")
    print("  output/quarantine/")
    print("  output/reports/day2_summary.csv")
    print("  output/kpis/kpi_11.csv")
    print("  output/kpis/kpi_12.csv")
    print("  output/kpis/kpi_13.csv")
    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run_day2()
