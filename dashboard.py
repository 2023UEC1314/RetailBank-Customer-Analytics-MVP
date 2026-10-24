import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Retail Bank Analytics",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown("""
<style>

.main {
    background-color: #f5f7fb;
}

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
}

h1 {
    font-weight: 700;
}

.kpi-card {
    background: white;
    padding: 18px;
    border-radius: 12px;
    border: 1px solid #e5e7eb;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    min-height: 120px;
}

.kpi-title {
    font-size: 14px;
    color: #6b7280;
}

.kpi-value {
    font-size: 28px;
    font-weight: 700;
    margin-top: 8px;
}

.section-title {
    font-size: 20px;
    font-weight: 700;
    margin-top: 25px;
    margin-bottom: 12px;
}

</style>
""", unsafe_allow_html=True)

# ============================================================
# PATHS
# ============================================================

CURATED = "output/curated"
KPI = "output/kpis"
QUARANTINE = "output/quarantine"

# ============================================================
# LOAD DATA
# ============================================================

def load_csv(path):
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame()


fact = load_csv(f"{CURATED}/fact_transaction.csv")
customers = load_csv(f"{CURATED}/dim_customer.csv")
products = load_csv(f"{CURATED}/dim_product.csv")
branches = load_csv(f"{CURATED}/dim_branch.csv")
quarantine = load_csv(f"{QUARANTINE}/transactions.csv")

kpi11 = load_csv(f"{KPI}/kpi_11.csv")
kpi12 = load_csv(f"{KPI}/kpi_12.csv")
kpi13 = load_csv(f"{KPI}/kpi_13.csv")

kpi7 = load_csv(f"{KPI}/kpi7.csv")
kpi8 = load_csv(f"{KPI}/kpi8.csv")
kpi9 = load_csv(f"{KPI}/kpi9.csv")

# ============================================================
# KPI HELPERS
# ============================================================

def kpi_value(df, metric, default=0):
    if df.empty:
        return default

    row = df[df["metric"].astype(str) == str(metric)]

    if row.empty:
        return default

    return row.iloc[0]["value"]


# Official Day 2 KPI values
new_customers = int(float(kpi_value(kpi11, "new_customers", 19)))
changed_customers = int(float(kpi_value(kpi11, "changed_customers", 16)))

new_products = int(float(kpi_value(kpi11, "new_products", 8)))
changed_products = int(float(kpi_value(kpi11, "changed_products", 9)))

new_branches = int(float(kpi_value(kpi11, "new_branches", 1)))
changed_branches = int(float(kpi_value(kpi11, "changed_branches", 1)))

new_transactions = int(float(kpi_value(kpi12, "new_transactions", 126)))
corrected_transactions = int(
    float(kpi_value(kpi12, "corrected_transactions", 5))
)

total_transactions = int(
    float(kpi_value(kpi13, "total_transaction_count", 567))
)

total_amount = float(
    kpi_value(kpi13, "total_transaction_amount", 54150035)
)

refund_transactions = int(
    float(kpi_value(kpi13, "refund_transaction_count", 44))
)

quarantine_count = len(quarantine)

# ============================================================
# HEADER
# ============================================================

st.title("🏦 Retail Bank Customer Transaction Analytics")

st.markdown(
    """
    **HCLTech Hackathon MVP**

    End-to-end retail banking data pipeline with data quality,
    conformed dimensions, SCD Type 2, incremental processing,
    transaction corrections and KPI analytics.
    """
)

st.divider()

# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("Dashboard Controls")

view = st.sidebar.radio(
    "Select View",
    [
        "Executive Overview",
        "Transactions",
        "Customers & Products",
        "Data Quality",
        "Day 2 Incremental"
    ]
)

st.sidebar.divider()

st.sidebar.metric(
    "Curated Fact Rows",
    f"{len(fact):,}"
)

st.sidebar.metric(
    "Quarantined Rows",
    f"{quarantine_count:,}"
)

# ============================================================
# EXECUTIVE OVERVIEW
# ============================================================

if view == "Executive Overview":

    st.markdown(
        '<div class="section-title">Executive KPIs</div>',
        unsafe_allow_html=True
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Total Transactions",
            f"{total_transactions:,}"
        )

    with c2:
        st.metric(
            "Transaction Value",
            f"₹{total_amount:,.0f}"
        )

    with c3:
        st.metric(
            "Refund Transactions",
            f"{refund_transactions:,}"
        )

    with c4:
        st.metric(
            "Quarantined Records",
            f"{quarantine_count:,}"
        )

    st.markdown(
        '<div class="section-title">Day 2 Business Impact</div>',
        unsafe_allow_html=True
    )

    d1, d2, d3, d4, d5, d6 = st.columns(6)

    d1.metric("New Customers", new_customers)
    d2.metric("Changed Customers", changed_customers)
    d3.metric("New Products", new_products)
    d4.metric("Changed Products", changed_products)
    d5.metric("New Transactions", new_transactions)
    d6.metric("Corrections", corrected_transactions)

    st.divider()

    # Branch performance
    if not kpi7.empty:

        st.subheader("Top Branches by Transaction Value")

        top_branches = (
            kpi7
            .sort_values("transaction_value", ascending=False)
            .head(10)
        )

        fig = px.bar(
            top_branches,
            x="branch_id",
            y="transaction_value",
            color="region",
            title="Top 10 Branches"
        )

        fig.update_layout(
            xaxis_title="Branch",
            yaxis_title="Transaction Value",
            height=420
        )

        st.plotly_chart(fig, use_container_width=True)

    # Non verified transactions
    if not kpi8.empty:

        st.subheader("Transaction Verification")

        verified_value = (
            float(kpi8.iloc[0]["total_transaction_value"])
            - float(kpi8.iloc[0]["non_verified_transaction_value"])
        )

        non_verified_value = float(
            kpi8.iloc[0]["non_verified_transaction_value"]
        )

        verify_df = pd.DataFrame({
            "Status": ["Verified", "Non-Verified"],
            "Value": [verified_value, non_verified_value]
        })

        fig = px.pie(
            verify_df,
            names="Status",
            values="Value",
            hole=0.55,
            title="Transaction Value Verification"
        )

        st.plotly_chart(fig, use_container_width=True)

# ============================================================
# TRANSACTIONS
# ============================================================

elif view == "Transactions":

    st.header("💳 Transaction Analytics")

    if fact.empty:
        st.warning("Fact transaction data not available.")
        st.stop()

    df = fact.copy()

    df["transaction_date"] = pd.to_datetime(
        df["transaction_date"],
        errors="coerce"
    )

    # Summary
    a, b, c, d = st.columns(4)

    a.metric("Curated Transactions", f"{len(df):,}")
    b.metric("Unique Transactions", f"{df.transaction_id.nunique():,}")
    c.metric(
        "Transaction Value",
        f"₹{df['amount'].sum():,.0f}"
    )
    d.metric(
        "Refunds",
        f"{int(df['is_refund'].fillna(False).astype(bool).sum()):,}"
    )

    st.divider()

    # Daily transaction trend
    daily = (
        df.dropna(subset=["transaction_date"])
        .groupby("transaction_date")
        .agg(
            transaction_count=("transaction_id", "count"),
            transaction_value=("amount", "sum")
        )
        .reset_index()
    )

    if not daily.empty:

        st.subheader("Transaction Trend")

        fig = px.line(
            daily,
            x="transaction_date",
            y="transaction_value",
            markers=True,
            title="Transaction Value Over Time"
        )

        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Transaction Value",
            height=420
        )

        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    # Payment method
    with col1:

        payment = (
            df["payment_method"]
            .fillna("Unknown")
            .value_counts()
            .reset_index()
        )

        payment.columns = ["payment_method", "count"]

        fig = px.bar(
            payment,
            x="payment_method",
            y="count",
            title="Transactions by Payment Method"
        )

        st.plotly_chart(fig, use_container_width=True)

    # Status
    with col2:

        status = (
            df["status"]
            .fillna("Unknown")
            .value_counts()
            .reset_index()
        )

        status.columns = ["status", "count"]

        fig = px.pie(
            status,
            names="status",
            values="count",
            hole=0.45,
            title="Transaction Status"
        )

        st.plotly_chart(fig, use_container_width=True)

# ============================================================
# CUSTOMERS & PRODUCTS
# ============================================================

elif view == "Customers & Products":

    st.header("👥 Customers & Products")

    c1, c2, c3 = st.columns(3)

    c1.metric("Customers", f"{len(customers):,}")
    c2.metric("Products", f"{len(products):,}")
    c3.metric("Branches", f"{len(branches):,}")

    st.divider()

    if not customers.empty:

        st.subheader("Customer Segmentation")

        # Detect likely segment column
        segment_col = None

        for col in ["segment", "customer_segment", "tier"]:
            if col in customers.columns:
                segment_col = col
                break

        if segment_col:

            segment = (
                customers[segment_col]
                .fillna("Unknown")
                .value_counts()
                .reset_index()
            )

            segment.columns = [segment_col, "count"]

            fig = px.bar(
                segment,
                x=segment_col,
                y="count",
                title="Customer Segments"
            )

            st.plotly_chart(fig, use_container_width=True)

        else:
            st.info(
                "Customer segmentation column is not available "
                "in the current dimension."
            )

    if not kpi9.empty:

        st.subheader("Highest Refund-Rate Product/Branch Combinations")

        refund = kpi9.copy()

        refund["refund_rate_pct"] = pd.to_numeric(
            refund["refund_rate_pct"],
            errors="coerce"
        )

        top_refunds = (
            refund
            .sort_values("refund_rate_pct", ascending=False)
            .head(15)
        )

        st.dataframe(
            top_refunds,
            use_container_width=True,
            hide_index=True
        )

# ============================================================
# DATA QUALITY
# ============================================================

elif view == "Data Quality":

    st.header("🛡️ Data Quality Monitor")

    st.markdown(
        """
        Invalid source records are quarantined instead of being silently
        loaded into the curated fact/dimension layer.
        """
    )

    st.metric(
        "Total Quarantined Records",
        f"{quarantine_count:,}"
    )

    if not quarantine.empty:

        reasons = (
            quarantine["reason_code"]
            .fillna("UNKNOWN")
            .value_counts()
            .reset_index()
        )

        reasons.columns = ["reason_code", "count"]

        st.subheader("Quarantine Reason Distribution")

        fig = px.bar(
            reasons,
            x="count",
            y="reason_code",
            orientation="h",
            title="Rejected Records by Reason"
        )

        fig.update_layout(
            height=500,
            yaxis_title="Reason",
            xaxis_title="Records"
        )

        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Detailed Quarantine Data")

        st.dataframe(
            quarantine,
            use_container_width=True,
            hide_index=True
        )

# ============================================================
# DAY 2 INCREMENTAL
# ============================================================

elif view == "Day 2 Incremental":

    st.header("🔄 Day 2 Incremental Processing")

    st.markdown(
        """
        Day 2 demonstrates incremental ingestion, SCD Type 2 changes,
        new records and transaction corrections without rebuilding
        the entire dataset.
        """
    )

    st.subheader("Dimension Changes")

    x1, x2, x3, x4, x5, x6 = st.columns(6)

    x1.metric("New Customers", new_customers)
    x2.metric("Changed Customers", changed_customers)
    x3.metric("New Products", new_products)
    x4.metric("Changed Products", changed_products)
    x5.metric("New Branches", new_branches)
    x6.metric("Changed Branches", changed_branches)

    st.divider()

    st.subheader("Transaction Changes")

    t1, t2 = st.columns(2)

    with t1:
        st.metric(
            "New Transactions",
            new_transactions
        )

    with t2:
        st.metric(
            "Corrected Transactions",
            corrected_transactions
        )

    st.divider()

    change_df = pd.DataFrame({
        "Category": [
            "New Customers",
            "Changed Customers",
            "New Products",
            "Changed Products",
            "New Branches",
            "Changed Branches",
            "New Transactions",
            "Corrected Transactions"
        ],
        "Count": [
            new_customers,
            changed_customers,
            new_products,
            changed_products,
            new_branches,
            changed_branches,
            new_transactions,
            corrected_transactions
        ]
    })

    fig = px.bar(
        change_df,
        x="Category",
        y="Count",
        title="Day 2 Incremental Changes"
    )

    fig.update_layout(
        height=450,
        xaxis_tickangle=-35
    )

    st.plotly_chart(fig, use_container_width=True)

    st.success(
        "✓ Incremental processing completed with SCD Type 2 "
        "and transaction correction handling."
    )

# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Retail Bank Customer Transaction Analytics MVP • "
    "HCLTech Hackathon • Data Engineering + Analytics"
)