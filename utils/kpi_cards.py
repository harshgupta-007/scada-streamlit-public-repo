import streamlit as st
import pandas as pd

def render_kpi_cards(df: pd.DataFrame):
    """
    Calculates and renders Key Performance Indicators (KPIs)
    with peak date & time intelligence.
    """
    if df.empty:
        st.warning("No data available for the selected period to display KPIs.")
        return
        
    st.subheader("Key Performance Indicators 📊")
    
    # Ensure datetime
    df['date'] = pd.to_datetime(df['date'])

    # -------------------------
    # 🔢 Basic Metrics
    # -------------------------
    total_energy = df['demand_energy'].sum()
    peak_demand = df['demand_energy'].max()
    avg_demand = df['demand_energy'].mean()

    # -------------------------
    # 🔥 Peak Info (IMPORTANT)
    # -------------------------
    peak_row = df.loc[df['demand_energy'].idxmax()]
    peak_block = int(peak_row['block_no'])
    peak_date = peak_row['date']

    # Convert block → time
    peak_minutes = (peak_block - 1) * 15
    peak_time = f"{peak_minutes // 60:02d}:{peak_minutes % 60:02d}"

    peak_date_str = peak_date.strftime("%d %b %Y")

    # -------------------------
    # 🌙 Min Info (NEW - useful)
    # -------------------------
    min_row = df.loc[df['demand_energy'].idxmin()]
    min_block = int(min_row['block_no'])
    min_date = min_row['date']
    min_value = min_row['demand_energy']

    min_minutes = (min_block - 1) * 15
    min_time = f"{min_minutes // 60:02d}:{min_minutes % 60:02d}"
    min_date_str = min_date.strftime("%d %b %Y")

    # -------------------------
    # 🧱 Layout
    # -------------------------
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Energy",
            value=f"{total_energy:,.0f} MWh",
            help="Total energy over selected period"
        )
        
    with col2:
        st.metric(
            label="Peak Demand",
            value=f"{peak_demand:,.0f} MW",
            delta=f"{peak_date_str} | {peak_time}",
            help="Maximum demand with timestamp"
        )
        
    with col3:
        st.metric(
            label="Minimum Demand",
            value=f"{min_value:,.0f} MW",
            delta=f"{min_date_str} | {min_time}",
            help="Minimum demand with timestamp"
        )
        
    with col4:
        st.metric(
            label="Average Demand",
            value=f"{avg_demand:,.0f} MW",
            help="Average demand across period"
        )
    
    st.markdown("---")
