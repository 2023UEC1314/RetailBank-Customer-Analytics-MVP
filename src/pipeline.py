import os, json, re
import pandas as pd
import numpy as np

DAY1 = "data/day1"
DAY2 = "data/day2"
OUT = "output"

def read_any(path):
    if path.lower().endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict):
            # accept common wrappers
            for k in ["products", "data", "records", "items"]:
                if k in obj and isinstance(obj[k], list):
                    obj = obj[k]
                    break
        return pd.DataFrame(obj)
    return pd.read_csv(path)

def find_file(folder, candidates):
    for name in candidates:
        p = os.path.join(folder, name)
        if os.path.exists(p):
            return p
    return None

def normalize_cols(df):
    df = df.copy()
    df.columns = [
        re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower())).strip("_")
        for c in df.columns
    ]
    return df

def rename_aliases(df, aliases):
    df = df.copy()
    for target, names in aliases.items():
        for n in names:
            if n in df.columns:
                df = df.rename(columns={n: target})
                break
    return df

def profile(df, name):
    return {
        "entity": name,
        "rows_received": int(len(df)),
        "columns": int(len(df.columns)),
        "null_cells": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum())
    }

def clean_text(s):
    return s.astype("string").str.strip()

def standardize_customer(df):
    aliases = {
        "customer_id":["customer_id","customerid","cust_id","custid"],
        "account_id":["account_id","accountid","account_no","account_number"],
        "name":["name","customer_name","full_name"],
        "gender":["gender","sex"],
        "email":["email","email_id","email_address"],
        "phone":["phone","mobile","mobile_no","phone_number"],
        "dob":["dob","date_of_birth","birth_date"],
        "kyc_status":["kyc_status","kyc","kycstatus"],
        "address":["address","customer_address"],
        "branch_id":["branch_id","branchid"],
        "product_id":["product_id","productid"],
    }
    df = rename_aliases(normalize_cols(df), aliases)
    for c in df.columns:
        if df[c].dtype == "object" or str(df[c].dtype).startswith("string"):
            df[c] = clean_text(df[c])
    if "gender" in df:
        df["gender"] = df["gender"].str.lower().map({
            "m":"Male","male":"Male","man":"Male",
            "f":"Female","female":"Female","woman":"Female",
            "o":"Other","other":"Other"
        }).fillna(df["gender"])
    if "kyc_status" in df:
        df["kyc_status"] = df["kyc_status"].str.lower().map({
            "verified":"Verified","verify":"Verified","yes":"Verified","y":"Verified",
            "pending":"Pending","no":"Not Verified","n":"Not Verified",
            "not verified":"Not Verified","unverified":"Not Verified"
        }).fillna(df["kyc_status"])
    if "dob" in df:
        df["dob"] = pd.to_datetime(df["dob"], errors="coerce")
    return df

def standardize_product(df):
    aliases = {
        "product_id":["product_id","productid","id"],
        "product_name":["product_name","name"],
        "category":["category","product_category","type"],
        "price":["price","amount","unit_price"],
        "is_active":["is_active","active","status"]
    }
    df = rename_aliases(normalize_cols(df), aliases)
    for c in df.columns:
        if df[c].dtype == "object":
            df[c] = clean_text(df[c])
    if "category" in df:
        df["category"] = df["category"].str.title()
    if "price" in df:
        df["price"] = (df["price"].astype("string")
                       .str.replace(r"[₹$,]", "", regex=True)
                       .str.replace(",", "", regex=False))
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
    if "is_active" in df:
        df["is_active"] = df["is_active"].astype("string").str.lower().map({
            "true":True,"1":True,"yes":True,"y":True,
            "false":False,"0":False,"no":False,"n":False
        })
    return df

def standardize_branch(df):
    aliases = {
        "branch_id":["branch_id","branchid","id"],
        "branch_name":["branch_name","name"],
        "region":["region","zone"],
        "branch_type":["branch_type","type"],
        "manager":["manager","manager_name"],
        "phone":["phone","phone_number","mobile"]
    }
    df = rename_aliases(normalize_cols(df), aliases)
    for c in df.columns:
        if df[c].dtype == "object":
            df[c] = clean_text(df[c])
    for c in ["region","branch_type"]:
        if c in df:
            df[c] = df[c].str.title()
    return df

def standardize_transaction(df):
    aliases = {
        "transaction_id":["transaction_id","transactionid","txn_id","txn"],
        "customer_id":["customer_id","customerid","cust_id"],
        "account_id":["account_id","accountid","account_no"],
        "branch_id":["branch_id","branchid"],
        "product_id":["product_id","productid"],
        "amount":["amount","transaction_amount","txn_amount","value"],
        "currency":["currency","ccy"],
        "transaction_date":["transaction_date","date","txn_date","transaction_datetime","timestamp"],
        "payment_method":["payment_method","paymentmode","payment_mode","method"],
        "status":["status","transaction_status","txn_status"],
        "is_refund":["is_refund","refund","refund_flag"]
    }
    df = rename_aliases(normalize_cols(df), aliases)
    for c in df.columns:
        if df[c].dtype == "object":
            df[c] = clean_text(df[c])
    if "amount" in df:
        df["amount"] = (df["amount"].astype("string")
                        .str.replace("₹","",regex=False)
                        .str.replace("$","",regex=False)
                        .str.replace(",","",regex=False)
                        .str.strip())
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    if "currency" in df:
        df["currency"] = df["currency"].str.upper()
    if "transaction_date" in df:
        df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    if "status" in df:
        df["status"] = df["status"].str.lower().map({
            "success":"SUCCESS","successful":"SUCCESS","completed":"SUCCESS",
            "failed":"FAILED","failure":"FAILED","pending":"PENDING",
            "cancelled":"CANCELLED","canceled":"CANCELLED"
        }).fillna(df["status"].str.upper())
    if "is_refund" in df:
        df["is_refund"] = df["is_refund"].astype("string").str.lower().map({
            "true":True,"1":True,"yes":True,"y":True,
            "false":False,"0":False,"no":False,"n":False
        }).fillna(False)
    else:
        df["is_refund"] = False
    return df

def quarantine_transactions(df, customers, branches, products):
    q = []
    valid = pd.Series(True, index=df.index)
    reasons = pd.Series("", index=df.index, dtype="string")

    def reject(mask, code):
        nonlocal valid, reasons
        new = mask & valid
        reasons.loc[new] = code
        valid.loc[new] = False

    if "transaction_id" in df:
        reject(df["transaction_id"].isna() | (df["transaction_id"] == ""), "MISSING_TRANSACTION_ID")
        dup = df["transaction_id"].duplicated(keep=False)
        reject(dup, "DUPLICATE_TRANSACTION_ID")
    if "amount" in df:
        reject(df["amount"].isna(), "INVALID_AMOUNT")
        reject(df["amount"] <= 0, "NON_POSITIVE_AMOUNT")
    if "currency" in df:
        reject(df["currency"].notna() & (df["currency"] != "INR"), "NON_INR_CURRENCY")
    if "transaction_date" in df:
        reject(df["transaction_date"].isna(), "INVALID_TRANSACTION_DATE")
        today = pd.Timestamp.now().normalize()
        reject(df["transaction_date"] > today, "FUTURE_TRANSACTION_DATE")

    for col, ref in [("customer_id", customers), ("branch_id", branches), ("product_id", products)]:
        if col in df and col in ref:
            missing = ~df[col].isin(ref[col].dropna().unique())
            reject(missing, f"ORPHAN_{col.upper()}")

    bad = df.loc[~valid].copy()
    if len(bad):
        bad["reason_code"] = reasons.loc[~valid].values
    good = df.loc[valid].copy()
    return good, bad

def build_dimensions(customers, products, branches):
    c = customers.copy()
    p = products.copy()
    b = branches.copy()
    c["customer_key"] = range(1, len(c)+1)
    p["product_key"] = range(1, len(p)+1)
    b["branch_key"] = range(1, len(b)+1)
    for df in [c,p,b]:
        df["effective_from"] = pd.Timestamp.now().normalize()
        df["effective_to"] = pd.NaT
        df["is_current"] = 1
    return c,p,b

def build_fact(txn, c, p, b):
    x = txn.copy()
    x = x.merge(c[["customer_id","customer_key"]], on="customer_id", how="left")
    x = x.merge(p[["product_id","product_key"]], on="product_id", how="left")
    x = x.merge(b[["branch_id","branch_key"]], on="branch_id", how="left")
    x["transaction_key"] = range(1, len(x)+1)
    cols = ["transaction_key","transaction_id","customer_key","product_key","branch_key",
            "customer_id","product_id","branch_id","account_id","amount","currency",
            "transaction_date","payment_method","status","is_refund"]
    cols = [c for c in cols if c in x.columns]
    return x[cols]

def kpis(fact, customer_dim, product_dim, branch_dim):
    x = fact.copy()

    if x.empty:
        empty = pd.DataFrame()
        return {
            "kpi1": empty, "kpi2": empty, "kpi3": empty,
            "kpi4": customer_dim.copy(), "kpi5": empty,
            "kpi6": empty, "kpi7": empty, "kpi8": empty, "kpi9": empty
        }

    x["net_amount"] = np.where(
        x["is_refund"], -x["amount"].abs(), x["amount"].abs()
    )

    # KPI 1
    k1 = (x.groupby("customer_id", as_index=False)
          .agg(net_transaction_volume=("net_amount","sum"),
               transaction_count=("transaction_id","count"))
          .sort_values(["net_transaction_volume","transaction_count"], ascending=[False,False])
          .head(5))

    # KPI 2
    k2 = x.copy()
    k2["month"] = pd.to_datetime(k2["transaction_date"]).dt.to_period("M").astype(str)
    k2 = (k2.groupby(["branch_id","month"], as_index=False)
          .agg(transaction_count=("transaction_id","count"), transaction_value=("net_amount","sum")))
    k2["mom_growth_pct"] = k2.groupby("branch_id")["transaction_value"].pct_change()*100

    # KPI 3
    k3 = x.groupby("product_id", as_index=False).agg(revenue=("net_amount","sum"))
    total = k3["revenue"].sum()
    k3["revenue_share_pct"] = np.where(total != 0, k3["revenue"]/total*100, 0)

    # KPI 4
    max_date = pd.to_datetime(x["transaction_date"]).max()
    active_accounts = set(x.loc[pd.to_datetime(x["transaction_date"]) >= max_date - pd.Timedelta(days=90), "account_id"].dropna())
    k4 = customer_dim[~customer_dim["account_id"].isin(active_accounts)].copy() if "account_id" in customer_dim else pd.DataFrame()

    # KPI 5
    x["txn_time"] = pd.to_datetime(x["transaction_date"])
    x["night_flag"] = x["txn_time"].dt.hour.between(0,4)
    x["large_flag"] = x["amount"] > 100000
    x = x.sort_values(["account_id","txn_time"])
    x["rolling_10m_count"] = (
        x.set_index("txn_time").groupby("account_id")["transaction_id"]
         .rolling("10min").count().reset_index(level=0, drop=True).values
    )
    k5 = x[(x["large_flag"]) | (x["night_flag"]) | (x["rolling_10m_count"] >= 3)].copy()
    k5["risk_reason"] = np.select(
        [k5["large_flag"] & k5["night_flag"],
         k5["large_flag"],
         k5["night_flag"],
         k5["rolling_10m_count"] >= 3],
        ["HIGH_VALUE_AND_NIGHT","HIGH_VALUE","NIGHT_TRANSACTION","3_PLUS_TXN_10_MIN"],
        default="OTHER"
    )

    # KPI 6
    max_date = pd.to_datetime(x["transaction_date"]).max()
    rfm = x.groupby("customer_id").agg(
        recency_days=("transaction_date", lambda s: (max_date - pd.to_datetime(s).max()).days),
        frequency=("transaction_id","count"),
        monetary=("net_amount","sum")
    ).reset_index()
    if len(rfm):
        rfm["r_score"] = pd.qcut(rfm["recency_days"].rank(method="first"), 3, labels=[3,2,1])
        rfm["f_score"] = pd.qcut(rfm["frequency"].rank(method="first"), 3, labels=[1,2,3])
        rfm["m_score"] = pd.qcut(rfm["monetary"].rank(method="first"), 3, labels=[1,2,3])
        rfm["score"] = rfm[["r_score","f_score","m_score"]].astype(int).sum(axis=1)
        rfm["segment"] = pd.cut(rfm["score"], bins=[0,4,7,8,10], labels=["Bronze","Silver","Gold","Platinum"], include_lowest=True)

    # KPI 7 - Branch performance ranking within region
    branch_values = x.groupby("branch_id", as_index=False).agg(
        transaction_value=("net_amount", "sum"),
        transaction_count=("transaction_id", "count")
    )
    if "region" in branch_dim.columns:
        region_map = branch_dim[["branch_id", "region"]].drop_duplicates("branch_id")
        k7 = branch_values.merge(region_map, on="branch_id", how="left")
        k7["rank_within_region"] = (
            k7.groupby("region")["transaction_value"]
              .rank(method="dense", ascending=False)
        )
        k7 = k7.sort_values(["region", "rank_within_region", "branch_id"])
    else:
        k7 = branch_values.copy()
        k7["rank_within_region"] = k7["transaction_value"].rank(
            method="dense", ascending=False
        )

    # KPI 8
    cx = x.merge(customer_dim[["customer_id","kyc_status"]].drop_duplicates("customer_id"),
                 on="customer_id", how="left")
    nonverified = cx[cx["kyc_status"].fillna("Not Verified") != "Verified"]
    k8 = pd.DataFrame([{
        "non_verified_transaction_value": nonverified["net_amount"].sum(),
        "total_transaction_value": cx["net_amount"].sum(),
        "non_verified_value_pct": (nonverified["net_amount"].sum()/cx["net_amount"].sum()*100
                                   if cx["net_amount"].sum() else 0)
    }])

    # KPI 9 - Refund rate by product and branch
    k9 = x.groupby(["product_id", "branch_id"], as_index=False).agg(
        total_txns=("transaction_id", "count"),
        refund_count=("is_refund", "sum"),
        total_value=("amount", "sum")
    )
    k9["refund_value"] = (
        x[x["is_refund"]]
        .groupby(["product_id", "branch_id"])["amount"]
        .sum()
        .reindex(pd.MultiIndex.from_frame(k9[["product_id", "branch_id"]]), fill_value=0)
        .to_numpy()
    )
    k9["refund_rate_pct"] = np.where(
        k9["total_txns"] > 0,
        k9["refund_count"] / k9["total_txns"] * 100,
        0
    )

    return {"kpi1":k1, "kpi2":k2, "kpi3":k3, "kpi4":k4, "kpi5":k5, "kpi6":rfm, "kpi7":k7, "kpi8":k8, "kpi9":k9}

def run_day1():
    os.makedirs(f"{OUT}/curated", exist_ok=True)
    os.makedirs(f"{OUT}/quarantine", exist_ok=True)
    os.makedirs(f"{OUT}/reports", exist_ok=True)
    os.makedirs(f"{OUT}/kpis", exist_ok=True)

    paths = {
        "customers": find_file(DAY1, ["customers.csv"]),
        "products": find_file(DAY1, ["products.json","products.csv"]),
        "branches": find_file(DAY1, ["branches.csv"]),
        "transactions": find_file(DAY1, ["transactions.csv"])
    }
    missing = [k for k,v in paths.items() if not v]
    if missing:
        raise FileNotFoundError("Missing Day 1 files: " + ", ".join(missing))

    c = standardize_customer(read_any(paths["customers"]))
    p = standardize_product(read_any(paths["products"]))
    b = standardize_branch(read_any(paths["branches"]))
    t = standardize_transaction(read_any(paths["transactions"]))

    # The Day 1 transaction file contains account_id but not customer_id.
    # Resolve customer_id from the customer master before DQ checks/fact loading.
    if "customer_id" not in t.columns and "account_id" in t.columns:
        account_to_customer = (
            c[["account_id", "customer_id"]]
            .dropna(subset=["account_id", "customer_id"])
            .drop_duplicates("account_id", keep="first")
        )
        t = t.merge(account_to_customer, on="account_id", how="left")

    profiles = pd.DataFrame([
        profile(c,"customers"), profile(p,"products"),
        profile(b,"branches"), profile(t,"transactions")
    ])
    profiles.to_csv(f"{OUT}/reports/data_profile.csv", index=False)

    # basic dimension deduplication
    if "customer_id" in c: c = c.drop_duplicates("customer_id", keep="first")
    if "product_id" in p: p = p.drop_duplicates("product_id", keep="first")
    if "branch_id" in b: b = b.drop_duplicates("branch_id", keep="first")

    good_t, bad_t = quarantine_transactions(
        t,
        c if "customer_id" in c else pd.DataFrame(columns=["customer_id"]),
        b if "branch_id" in b else pd.DataFrame(columns=["branch_id"]),
        p if "product_id" in p else pd.DataFrame(columns=["product_id"])
    )
    bad_t.to_csv(f"{OUT}/quarantine/transactions.csv", index=False)

    c,p,b = build_dimensions(c,p,b)
    fact = build_fact(good_t,c,p,b)

    c.to_csv(f"{OUT}/curated/dim_customer.csv", index=False)
    p.to_csv(f"{OUT}/curated/dim_product.csv", index=False)
    b.to_csv(f"{OUT}/curated/dim_branch.csv", index=False)
    fact.to_csv(f"{OUT}/curated/fact_transaction.csv", index=False)

    results = kpis(fact,c,p,b)
    for name, df in results.items():
        df.to_csv(f"{OUT}/kpis/{name}.csv", index=False)

    scorecard = pd.DataFrame([
        {"entity":"customers","received":len(c),"passed":len(c),"rejected":0},
        {"entity":"products","received":len(p),"passed":len(p),"rejected":0},
        {"entity":"branches","received":len(b),"passed":len(b),"rejected":0},
        {"entity":"transactions","received":len(t),"passed":len(good_t),"rejected":len(bad_t)}
    ])
    scorecard.to_csv(f"{OUT}/reports/dq_scorecard.csv", index=False)
    print("Day 1 pipeline complete.")
    print(scorecard.to_string(index=False))

if __name__ == "__main__":
    run_day1()
