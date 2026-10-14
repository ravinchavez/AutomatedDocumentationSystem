# pages/financial_overview_page.py
from datetime import date, timedelta
from calendar import monthrange

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from clients.supabase_client import list_receipts


@st.cache_data(ttl=60)
def _load_receipts() -> pd.DataFrame:
    """Pull all receipts for the current user and normalize to a DataFrame."""
    rows = list_receipts(order_by="transaction_date", desc=True)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df["documentation_date"] = pd.to_datetime(
        df["documentation_date"], errors="coerce"
    )
    df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce").fillna(0)
    df["category"] = df["category"].fillna("Uncategorized")
    df["merchant_id"] = df.get("merchant_id", pd.Series(dtype=str)).fillna("Unknown")
    df = df.dropna(subset=["transaction_date"])
    return df.sort_values("transaction_date", ascending=False)


def _filter_range(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    mask = (df["transaction_date"].dt.date >= start) & (
        df["transaction_date"].dt.date <= end
    )
    return df.loc[mask].copy()


def _range_for_period(period: str) -> tuple[date, date, str]:
    today = date.today()
    if period == "Weekly":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        label = f"{start:%b %d} – {end:%b %d, %Y}"
    elif period == "Monthly":
        start = today.replace(day=1)
        end = today.replace(day=monthrange(today.year, today.month)[1])
        label = f"{start:%B %Y}"
    else:  # Lifetime
        start = date(1970, 1, 1)
        end = today
        label = "All time"
    return start, end, label


def _totals(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"total": 0.0, "count": 0, "avg": 0.0, "days": 0, "per_day": 0.0}
    total = float(df["total_amount"].sum())
    count = int(len(df))
    days = max(
        (df["transaction_date"].max() - df["transaction_date"].min()).days + 1, 1
    )
    return {
        "total": total,
        "count": count,
        "avg": total / count if count else 0.0,
        "days": days,
        "per_day": total / days,
    }


def _kpi_row(totals: dict, currency: str) -> None:
    metrics = [
        ("Total spent", f"{currency} {totals['total']:,.2f}"),
        ("Transactions", f"{totals['count']}"),
        ("Avg per receipt", f"{currency} {totals['avg']:,.2f}"),
        ("Avg per day", f"{currency} {totals.get('per_day', 0):,.2f}"),
    ]

    cols = st.columns(2)
    for i, (label, value) in enumerate(metrics):
        col = cols[i % 2]
        col.metric(label, value)


def _pie_by_category(df: pd.DataFrame, currency: str, key_suffix: str = "") -> None:
    if df.empty:
        st.info("No data in this range.")
        return
    agg = (
        df.groupby("category", as_index=False)["total_amount"]
        .sum()
        .sort_values("total_amount", ascending=False)
    )
    fig = px.pie(
        agg,
        names="category",
        values="total_amount",
        hole=0.45,
        title=f"Spending by category ({currency})",
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>%{value:,.2f}<br>%{percent}<extra></extra>",
    )
    fig.update_layout(showlegend=True, height=420, margin=dict(t=60, b=20))
    st.plotly_chart(
        fig,
        use_container_width=True,
        key=f"pie_category_{key_suffix}",
    )


def _line_over_time(df: pd.DataFrame, currency: str, period: str) -> None:
    if df.empty:
        return

    freq = "D" if period in ("Weekly", "Monthly") else "W"
    series = (
        df.set_index("transaction_date")
        .resample(freq)["total_amount"]
        .sum()
        .reset_index()
    )

    fig = px.line(
        series,
        x="transaction_date",
        y="total_amount",
        markers=True,
        title=f"Spending over time ({currency})",
    )
    fig.update_traces(
        line=dict(width=3),
        hovertemplate="%{x|%b %d, %Y}<br>%{y:,.2f}<extra></extra>",
    )
    fig.update_layout(
        height=380,
        xaxis_title="Date",
        yaxis_title=f"Amount ({currency})",
        hovermode="x unified",
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
        key=f"line_over_time_{period.lower()}",
    )


def _bar_by_merchant(
    df: pd.DataFrame, 
    currency: str, 
    period: str, 
    top_n: int = 10) -> None:
    if df.empty:
        return
    agg = (
        df.groupby("merchant_id", as_index=False)["total_amount"]
        .sum()
        .sort_values("total_amount", ascending=False)
        .head(top_n)
    )
    fig = px.bar(
        agg,
        x="total_amount",
        y="merchant_id",
        orientation="h",
        title=f"Top {top_n} merchants ({currency})",
    )
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>%{x:,.2f}<extra></extra>",
    )
    fig.update_layout(
        height=420,
        yaxis=dict(autorange="reversed"),
        xaxis_title=f"Amount ({currency})",
        yaxis_title="",
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
        key=f"bar_merchant_{period.lower()}",
    )


def _sankey_flow(df: pd.DataFrame, 
                 currency: str, 
                 period: str) -> None:
    if df.empty:
        st.info("No data for a Sankey flow.")
        return

    trimmed = df.copy()
    top_cats = (
        trimmed.groupby("category")["total_amount"].sum()
        .sort_values(ascending=False).head(8).index
    )
    trimmed = trimmed[trimmed["category"].isin(top_cats)]

    top_merchants = (
        trimmed.groupby("merchant_id")["total_amount"].sum()
        .sort_values(ascending=False).head(12).index
    )
    trimmed = trimmed[trimmed["merchant_id"].isin(top_merchants)]

    edges = (
        trimmed.groupby(["category", "merchant_id"], as_index=False)["total_amount"]
        .sum()
    )

    cats = list(edges["category"].unique())
    merchs = list(edges["merchant_id"].unique())
    labels = cats + merchs
    cat_idx = {c: i for i, c in enumerate(cats)}
    merch_idx = {m: i + len(cats) for i, m in enumerate(merchs)}

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                pad=15,
                thickness=18,
                line=dict(color="rgba(0,0,0,0.2)", width=0.5),
                label=labels,
                color="rgba(100,150,220,0.8)",
            ),
            link=dict(
                source=[cat_idx[c] for c in edges["category"]],
                target=[merch_idx[m] for m in edges["merchant_id"]],
                value=edges["total_amount"].tolist(),
                hovertemplate="%{source.label} → %{target.label}<br>"
                              "%{value:,.2f}<extra></extra>",
            ),
        )
    )
    fig.update_layout(
        title=f"Money flow: Category → Merchant ({currency})",
        height=560,
        margin=dict(t=60, b=20, l=20, r=20),
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
        key=f"sankey_flow_{period.lower()}",
    )


def _detail_table(df: pd.DataFrame) -> None:
    if df.empty:
        return
    show = df[
        [
            "transaction_date",
            "merchant_id",
            "category",
            "currency",
            "total_amount",
            "or_number",
            "description",
        ]
    ].copy()
    show["transaction_date"] = show["transaction_date"].dt.strftime("%Y-%m-%d")
    st.dataframe(
        show.sort_values("transaction_date", ascending=False),
        use_container_width=True,
        hide_index=True,
    )


def financial_overview_page():
    st.title("Financial Overview")

    df_all = _load_receipts()
    if df_all.empty:
        st.info("No receipts yet. Add some entries first.")
        return

    with st.sidebar:
        st.subheader("Filters")
        all_categories = sorted(df_all["category"].unique().tolist())
        picked_categories = st.multiselect(
            "Categories",
            options=all_categories,
            default=all_categories,
            key="dash_categories",
        )
        all_currencies = sorted(df_all["currency"].dropna().unique().tolist())
        picked_currencies = st.multiselect(
            "Currencies",
            options=all_currencies,
            default=all_currencies,
            key="dash_currencies",
        )

    df = df_all[
        df_all["category"].isin(picked_categories)
        & df_all["currency"].isin(picked_currencies)
    ].copy()

    if df.empty:
        st.warning("No receipts match the current filters.")
        return

    # ---- Tabs ----
    tab_week, tab_month, tab_life = st.tabs(["Weekly", "Monthly", "Lifetime"])

    for tab, period in [
        (tab_week, "Weekly"),
        (tab_month, "Monthly"),
        (tab_life, "Lifetime"),
    ]:
        with tab:
            start, end, label = _range_for_period(period)
            sub = _filter_range(df, start, end)

            st.caption(f"**{label}** · {len(sub)} transactions")

            if sub.empty:
                st.info("No receipts in this window.")
                continue

            # dominant currency for KPI labels
            currency = sub["currency"].mode().iloc[0] if not sub.empty else "—"

            _kpi_row(_totals(sub), currency)

            st.divider()

            left, right = st.columns([1, 1])
            with left:
                _pie_by_category(sub, currency, key_suffix=period.lower())
            with right:
                _line_over_time(sub, currency, period)

            st.divider()

            _sankey_flow(sub, currency, period)

            st.divider()

            _bar_by_merchant(sub, currency, period)

            with st.expander("Receipt details"):
                _detail_table(sub)