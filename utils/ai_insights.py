import os
import pandas as pd
from utils.charts import get_peak_info, block_to_time,calculate_regional_contribution,calculate_ramp




# -----------------------------
# 🔹 Build Intraday Summary
# -----------------------------
def build_intraday_summary(df):
    df['date'] = pd.to_datetime(df['date'])

    peak = get_peak_info(df)

    peak_time = block_to_time(peak['peak_block'])
    peak_date = pd.to_datetime(peak['peak_date']).strftime("%d %b %Y")

    avg_demand = df['demand_energy'].mean()

    flags_text = ""
    if 'is_weekend' in df.columns and df['is_weekend'].any():
        flags_text += "\n    [Notice: Weekend Detected in Data]"
    if 'is_holiday' in df.columns and df['is_holiday'].any():
        flags_text += "\n    [Notice: Holiday Detected in Data]"
    if 'is_special_event' in df.columns and df['is_special_event'].any():
        events = df.loc[df['is_special_event'], 'event_description'].dropna().unique()
        if len(events) > 0:
            flags_text += f"\n    [Special Events Triggered: {', '.join(events)}]"

    return f"""
    Intraday Demand Summary:

    Peak Demand: {peak['peak_value']:.0f} MW
    Peak Time: {peak_time}
    Peak Date: {peak_date}

    Average Demand: {avg_demand:.0f} MW{flags_text}
    """

def build_regional_summary(df):
    df_pct = calculate_regional_contribution(df)

    latest = df_pct.iloc[-1]

    return f"""
    Regional Demand Summary:

    CZ Contribution: {latest['CZ_Demand_pct']:.1f}%
    EZ Contribution: {latest['EZ_Demand_pct']:.1f}%
    WZ Contribution: {latest['WZ_Demand_pct']:.1f}%

    Total demand distribution varies across regions.
    """


def build_ramp_summary(df):
    df_ramp = calculate_ramp(df)

    max_ramp = df_ramp.loc[df_ramp['ramp'].idxmax()]
    min_ramp = df_ramp.loc[df_ramp['ramp'].idxmin()]

    max_block = int(max_ramp['block_no'])
    min_block = int(min_ramp['block_no'])

    max_time = block_to_time(max_block)
    min_time = block_to_time(min_block)

    max_date = pd.to_datetime(max_ramp['date']).strftime("%d %b %Y")
    min_date = pd.to_datetime(min_ramp['date']).strftime("%d %b %Y")

    return f"""
    Ramp Summary:

    Maximum Ramp-Up: {max_ramp['ramp']:.0f} MW at {max_time} on {max_date}
    Maximum Ramp-Down: {min_ramp['ramp']:.0f} MW at {min_time} on {min_date}

    Significant variation in demand observed across time blocks.
    """


def build_weather_summary(df, zone):
    demand_col = f"{zone}_Demand"
    temp_col = f"{zone}_temperature"
    if demand_col not in df.columns: demand_col = 'demand_energy'
    if temp_col not in df.columns: temp_col = 'temperature'
        
    try:
        correlation = df[demand_col].corr(df[temp_col])
        avg_temp = df[temp_col].mean()
        avg_demand = df[demand_col].mean()
    except:
        correlation, avg_temp, avg_demand = 0, 0, 0

    flags_text = ""
    if 'is_weekend' in df.columns and df['is_weekend'].any():
        flags_text += "\n    [Notice: Weekend Data Present]"
    if 'is_holiday' in df.columns and df['is_holiday'].any():
        flags_text += "\n    [Notice: Holiday Data Present]"
    if 'is_special_event' in df.columns and df['is_special_event'].any():
        events = df.loc[df['is_special_event'], 'event_description'].dropna().unique()
        if len(events) > 0:
            flags_text += f"\n    [Notice: Special Event: {', '.join(events)}]"

    return f"""
    Weather & Demand Summary for {zone}:
    
    Average Demand: {avg_demand:.0f} MW
    Average Temperature: {avg_temp:.1f} °C
    Demand-Temperature Correlation: {correlation:.2f}{flags_text}
    """