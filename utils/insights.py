from utils.charts import (
    get_peak_info,
    block_to_time,
    calculate_regional_contribution,
    calculate_variability,
    calculate_ramp
)


import pandas as pd
def generate_master_insights(df):
    if df.empty:
        return ["No data available."]

    insights = []

    # Ensure datetime
    df['date'] = pd.to_datetime(df['date'])

    # -------------------
    # 🔥 Intraday Insight (WITH DATE)
    # -------------------
    peak_info = get_peak_info(df)

    peak_time = block_to_time(peak_info['peak_block'])
    peak_date = pd.to_datetime(peak_info['peak_date']).strftime("%d %b %Y")

    insights.append(
        f"🔥 Peak demand of {peak_info['peak_value']:.0f} MW observed on {peak_date} at {peak_time} (Block {peak_info['peak_block']})."
    )

    # -------------------
    # 🌍 Regional Insight
    # -------------------
    df_pct = calculate_regional_contribution(df)
    latest = df_pct.iloc[-1]

    regions = {
        "CZ": latest['CZ_Demand_pct'],
        "EZ": latest['EZ_Demand_pct'],
        "WZ": latest['WZ_Demand_pct']
    }

    dominant_region = max(regions, key=regions.get)

    insights.append(
        f"🌍 {dominant_region} region dominates demand with {regions[dominant_region]:.1f}% contribution."
    )

    # -------------------
    # ⚠️ Variability Insight
    # -------------------
    variability = calculate_variability(df)
    overall_cv = variability['demand_energy']['cv']

    if overall_cv > 0.2:
        risk = "high"
    elif overall_cv > 0.1:
        risk = "moderate"
    else:
        risk = "low"

    insights.append(
        f"⚠️ Demand variability is {risk} (CV = {overall_cv:.2f})."
    )

    # -------------------
    # ⚡ Ramp Insight (WITH UP & DOWN)
    # -------------------
    df_ramp = calculate_ramp(df)

    # Max ramp-up
    max_ramp_row = df_ramp.loc[df_ramp['ramp'].idxmax()]
    ramp_up_value = max_ramp_row['ramp']
    ramp_up_block = int(max_ramp_row['block_no'])
    ramp_up_date = pd.to_datetime(max_ramp_row['date']).strftime("%d %b %Y")
    ramp_up_time = block_to_time(ramp_up_block)

    # Max ramp-down
    min_ramp_row = df_ramp.loc[df_ramp['ramp'].idxmin()]
    ramp_down_value = min_ramp_row['ramp']
    ramp_down_block = int(min_ramp_row['block_no'])
    ramp_down_date = pd.to_datetime(min_ramp_row['date']).strftime("%d %b %Y")
    ramp_down_time = block_to_time(ramp_down_block)

    insights.append(
        f"⚡ Maximum ramp-up of {ramp_up_value:.0f} MW observed on {ramp_up_date} at {ramp_up_time} (Block {ramp_up_block})."
    )

    insights.append(
        f"🔻 Maximum ramp-down of {ramp_down_value:.0f} MW observed on {ramp_down_date} at {ramp_down_time} (Block {ramp_down_block})."
    )
    return insights

def generate_weather_insights(df: pd.DataFrame, zone: str = 'WZ', selected_date=None):
    if df.empty:
        return "Not enough data for weather insights."
        
    demand_col = f"{zone}_Demand"
    temp_col = f"{zone}_temperature"
    
    # Generic fallback
    if demand_col not in df.columns: demand_col = 'demand_energy'
    if temp_col not in df.columns: temp_col = 'temperature'
        
    if demand_col not in df.columns or temp_col not in df.columns:
        return f"Weather data for {zone} is incomplete."
        
    # Correlation
    try:
        correlation = df[demand_col].corr(df[temp_col])
    except:
        correlation = 0
    
    # Extreme days comparison
    df_daily = df.groupby('date')[[demand_col, temp_col]].mean().reset_index()
    if df_daily.empty or len(df_daily) < 2:
        return "Insufficient daily data to determine extreme weather impacts."
        
    avg_temp = df_daily[temp_col].mean()
    
    day_insight = ""
    if selected_date is not None:
        try:
            day_data = df_daily[df_daily['date'].dt.date == selected_date]
            if not day_data.empty:
                day_temp = day_data.iloc[0][temp_col]
                day_demand = day_data.iloc[0][demand_col]
                temp_diff = day_temp - avg_temp
                direction = "higher 🔺" if temp_diff > 0 else "lower 🔻"
                
                day_insight += f"📅 **Analysis for {selected_date.strftime('%B %d, %Y')}**:\n"
                day_insight += f"- Average Temperature: **{day_temp:.1f}°C** ({abs(temp_diff):.1f}°C {direction} than the period average of {avg_temp:.1f}°C)\n"
                day_insight += f"- Average Demand: **{day_demand:.0f} MW**\n\n"
        except Exception:
            pass
            
    high_temp_days = df_daily[df_daily[temp_col] > avg_temp + 2]
    normal_temp_days = df_daily[df_daily[temp_col] <= avg_temp + 2]
    
    elasticity_insight = "🌡️ Temperature variations are stable in the selected period."
    if not high_temp_days.empty and not normal_temp_days.empty:
        high_demand_avg = high_temp_days[demand_col].mean()
        normal_demand_avg = normal_temp_days[demand_col].mean()
        diff_pct = ((high_demand_avg - normal_demand_avg) / normal_demand_avg) * 100
        
        if diff_pct > 0:
            elasticity_insight = f"🔴 On extremely hot days (> {avg_temp + 2:.1f}°C), {zone} demand increases by **{diff_pct:.1f}%** compared to normal days."

    correlation_text = "strong positive" if correlation > 0.6 else "moderate positive" if correlation > 0.3 else "weak" if correlation > -0.3 else "negative"
    
    return f"{day_insight}📈 **Demand-Temperature Correlation**: {zone} shows a **{correlation_text}** correlation ({correlation:.2f}) with temperature.\n\n{elasticity_insight}"



