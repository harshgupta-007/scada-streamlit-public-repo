import pandas as pd
import streamlit as st


def render_kpi_cards(df: pd.DataFrame):
    """Render key SCADA KPIs with peak and minimum timing context."""
    if df.empty:
        st.warning("No data available for the selected period to display KPIs.")
        return

    st.subheader("Key Performance Indicators")

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    # The dataset is block-level demand in MW. Each block represents 15 minutes,
    # so energy in MWh is MW * 0.25 hours.
    total_energy_gwh = (df["demand_energy"].sum() * 0.25) / 1000
    peak_demand = df["demand_energy"].max()
    avg_demand = df["demand_energy"].mean()

    peak_row = df.loc[df["demand_energy"].idxmax()]
    peak_block = int(peak_row["block_no"])
    peak_date = peak_row["date"]
    peak_minutes = (peak_block - 1) * 15
    peak_time = f"{peak_minutes // 60:02d}:{peak_minutes % 60:02d}"
    peak_date_str = peak_date.strftime("%d %b %Y")

    min_row = df.loc[df["demand_energy"].idxmin()]
    min_block = int(min_row["block_no"])
    min_date = min_row["date"]
    min_value = min_row["demand_energy"]
    min_minutes = (min_block - 1) * 15
    min_time = f"{min_minutes // 60:02d}:{min_minutes % 60:02d}"
    min_date_str = min_date.strftime("%d %b %Y")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Energy",
            value=f"{total_energy_gwh:,.1f} GWh",
        )

    with col2:
        st.metric(
            label="Peak Demand",
            value=f"{peak_demand:,.0f} MW",
            delta=f"{peak_date_str} | {peak_time}",
        )

    with col3:
        st.metric(
            label="Minimum Demand",
            value=f"{min_value:,.0f} MW",
            delta=f"{min_date_str} | {min_time}",
        )

    with col4:
        st.metric(
            label="Average Demand",
            value=f"{avg_demand:,.0f} MW",
        )

    st.markdown("---")
