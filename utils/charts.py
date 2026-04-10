import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from utils.data_loader import get_daily_aggregations,get_intraday_profile

def plot_demand_trend(df: pd.DataFrame):
    """Plots the total daily demand energy over time."""
    if df.empty:
        return None
    daily_demand = get_daily_aggregations(df)
    
    fig = px.line(
        daily_demand, 
        x='date', 
        y='demand_energy', 
        title='Total Daily Demand Energy Over Time',
        labels={'demand_energy': 'Total Demand (MWh)', 'date': 'Date'}
    )
    fig.update_layout(template='plotly_white', hovermode='x unified')
    return fig

def plot_demand_stats(df: pd.DataFrame):
    """Plots daily peak, min, and average demand."""
    if df.empty:
        return None
    daily_stats = get_daily_aggregations(df)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=daily_stats['date'], y=daily_stats['peak_demand'], mode='lines', name='Peak Demand'))
    fig.add_trace(go.Scatter(x=daily_stats['date'], y=daily_stats['avg_demand'], mode='lines', name='Avg Demand'))
    fig.add_trace(go.Scatter(x=daily_stats['date'], y=daily_stats['min_demand'], mode='lines', name='Min Demand'))

    fig.update_layout(
        title='Daily Peak, Min, and Average Demand',
        xaxis_title='Date',
        yaxis_title='Demand (MW)',
        template='plotly_white',
        hovermode='x unified'
    )
    return fig

def plot_regional_distribution(df: pd.DataFrame):
    """Plots a boxplot of regional demand."""
    if df.empty:
        return None
        
    region_cols = ['CZ_Demand', 'EZ_Demand', 'WZ_Demand', 'demand_energy']
    # Melt the dataframe
    df_regions = df.melt(id_vars=['date', 'block_no'], value_vars=region_cols, var_name='Region', value_name='Demand')
    
    fig = px.box(
        df_regions, 
        x='Region', 
        y='Demand', 
        title='Demand Distribution by Region',
        color='Region',
        template='plotly_white'
    )
    return fig

def plot_regional_trend(df: pd.DataFrame):
    if df.empty:
        return None

    region_cols = ['CZ_Demand', 'EZ_Demand', 'WZ_Demand', 'demand_energy']

    # ✅ Aggregate to ONE value per date
    df_daily = df.groupby('date')[region_cols].sum().reset_index()

    # Melt
    df_regions = df_daily.melt(
        id_vars='date',
        value_vars=region_cols,
        var_name='Region',
        value_name='Demand'
    )

    # Plot
    fig = px.line(
        df_regions,
        x='date',
        y='Demand',
        color='Region',
        title='Regional Demand Trend Over Time',
        markers=True
    )

    fig.update_layout(template='plotly_white', hovermode='x unified')
    return fig

def plot_generation_mix(df: pd.DataFrame):
    """Plots an area chart of the generation mix over time."""
    if df.empty:
        return None
        
    gen_cols = ['thermal_gen', 'hydel_gen', 'renewable_gen']
    # Sum up generation per day directly from the daily sum 
    # (or sum it if plotting raw blocks, but area chart usually makes more sense daily)
    daily_gen = get_daily_aggregations(df)
    
    fig = go.Figure()
    for col in gen_cols:
        fig.add_trace(go.Scatter(
            x=daily_gen['date'], 
            y=daily_gen[col],
            mode='lines',
            name=col.replace('_', ' ').title(),
            stackgroup='one'
        ))

    fig.update_layout(
        title='Total Generation Mix Over Time',
        xaxis_title='Date',
        yaxis_title='Generation (MWh)',
        template='plotly_white',
        hovermode='x unified'
    )
    return fig

def plot_intraday_profile(df: pd.DataFrame):
    """Plots the average demand profile by block."""
    if df.empty:
        return None
        
    avg_block_profile = df.groupby('block_no')['demand_energy'].mean().reset_index()

    fig = px.line(
        avg_block_profile, 
        x='block_no', 
        y='demand_energy', 
        title='Average Intraday Demand Profile',
        labels={'demand_energy': 'Average Demand (MW)', 'block_no': 'Time Block (1-96)'}
    )
    fig.update_layout(template='plotly_white')
    return fig

# start here one by one

import plotly.express as px

def plot_intraday_curve(df: pd.DataFrame):
    if df.empty:
        return None

    profile = get_intraday_profile(df)

    fig = px.line(
        profile,
        x='block_no',
        y='demand_energy',
        title='Intraday Demand Profile (96 Blocks)',
        labels={'block_no': 'Time Block', 'demand_energy': 'Demand (MW)'},
        markers=True
    )

    fig.update_layout(template='plotly_white')

    return fig

# def get_peak_info(df: pd.DataFrame):
#     profile = get_intraday_profile(df)

#     peak_row = profile.loc[profile['demand_energy'].idxmax()]
#     min_row = profile.loc[profile['demand_energy'].idxmin()]

#     return {
#         "peak_block": int(peak_row['block_no']),
#         "peak_value": peak_row['demand_energy'],
#         "min_block": int(min_row['block_no']),
#         "min_value": min_row['demand_energy']
#     }

def get_peak_info(df: pd.DataFrame):
    if df.empty:
        return None

    # 🔥 Find actual peak row (NOT aggregated)
    peak_row = df.loc[df['demand_energy'].idxmax()]
    min_row = df.loc[df['demand_energy'].idxmin()]

    return {
        "peak_block": int(peak_row['block_no']),
        "peak_value": peak_row['demand_energy'],
        "peak_date": peak_row['date'],

        "min_block": int(min_row['block_no']),
        "min_value": min_row['demand_energy'],
        "min_date": min_row['date']
    }

def block_to_time(block):
    minutes = (block - 1) * 15
    hours = minutes // 60
    mins = minutes % 60
    return f"{int(hours):02d}:{int(mins):02d}"

def generate_intraday_insights(df):
    info = get_peak_info(df)

    peak_time = block_to_time(info['peak_block'])
    min_time = block_to_time(info['min_block'])

    peak_date = pd.to_datetime(info['peak_date']).strftime("%d %b %Y")
    min_date = pd.to_datetime(info['min_date']).strftime("%d %b %Y")

    return f"""
    🔥 Peak demand of {info['peak_value']:.0f} MW observed on {peak_date} at {peak_time} (Block {info['peak_block']}).

    🌙 Minimum demand of {info['min_value']:.0f} MW observed on {min_date} at {min_time} (Block {info['min_block']}).

    ⚡ Significant ramp-up likely occurs before peak hours — important for scheduling.
    """
def calculate_regional_contribution(df: pd.DataFrame):
    if df.empty:
        return None

    region_cols = ['CZ_Demand', 'EZ_Demand', 'WZ_Demand']

    # Aggregate daily
    df_daily = df.groupby('date')[region_cols + ['demand_energy']].sum().reset_index()

    # Calculate %
    for col in region_cols:
        df_daily[col + "_pct"] = (df_daily[col] / df_daily['demand_energy']) * 100

    return df_daily

def plot_regional_contribution(df: pd.DataFrame):
    df_pct = calculate_regional_contribution(df)

    if df_pct is None:
        return None

    # Melt for plotting
    df_melt = df_pct.melt(
        id_vars='date',
        value_vars=['CZ_Demand_pct', 'EZ_Demand_pct', 'WZ_Demand_pct'],
        var_name='Region',
        value_name='Contribution'
    )

    # Clean names
    df_melt['Region'] = df_melt['Region'].str.replace('_Demand_pct', '')

    fig = px.area(
        df_melt,
        x='date',
        y='Contribution',
        color='Region',
        title='Regional Contribution to Total Demand (%)'
    )

    fig.update_layout(template='plotly_white', hovermode='x unified')

    return fig


def generate_regional_insights(df: pd.DataFrame):
    df_pct = calculate_regional_contribution(df)

    latest = df_pct.iloc[-1]

    contributions = {
        "CZ": latest['CZ_Demand_pct'],
        "EZ": latest['EZ_Demand_pct'],
        "WZ": latest['WZ_Demand_pct']
    }

    dominant_region = max(contributions, key=contributions.get)

    return f"""
    🌍 {dominant_region} region is contributing the highest demand ({contributions[dominant_region]:.1f}%).

    📊 Regional demand distribution is relatively {'balanced' if max(contributions.values()) < 50 else 'skewed'}.

    ⚡ Monitoring dominant regions is critical for load management and infrastructure planning.
    """

# Step 3.1: Variability Calculation

def calculate_variability(df: pd.DataFrame):
    if df.empty:
        return None

    region_cols = ['CZ_Demand', 'EZ_Demand', 'WZ_Demand', 'demand_energy']

    variability = {}

    for col in region_cols:
        variability[col] = {
            "mean": df[col].mean(),
            "std": df[col].std(),
            "cv": df[col].std() / df[col].mean() if df[col].mean() != 0 else 0
        }

    return variability


def plot_variability(df: pd.DataFrame):
    variability = calculate_variability(df)

    if variability is None:
        return None

    df_var = pd.DataFrame(variability).T.reset_index()
    df_var.columns = ['Region', 'Mean', 'Std Dev', 'CV']

    fig = px.bar(
        df_var,
        x='Region',
        y='Std Dev',
        title='Demand Variability (Standard Deviation)',
        text='Std Dev'
    )

    fig.update_layout(template='plotly_white')

    return fig


def generate_variability_insights(df: pd.DataFrame):
    variability = calculate_variability(df)

    # Find most volatile region
    max_region = max(variability, key=lambda x: variability[x]['std'])

    # Check overall system variability
    overall_cv = variability['demand_energy']['cv']

    risk_level = "Low"
    if overall_cv > 0.2:
        risk_level = "High"
    elif overall_cv > 0.1:
        risk_level = "Moderate"

    return f"""
    ⚠️ {max_region} shows highest variability — requires close monitoring.

    📊 Overall system variability is {risk_level} (CV = {overall_cv:.2f}).

    ⚡ High variability can impact forecasting accuracy and increase procurement cost.
    """

##⚡ Step 4: Ramp Analysis (🔥 High Impact)

def get_ramp_profile(df: pd.DataFrame):
    df_ramp = calculate_ramp(df)

    profile = df_ramp.groupby('block_no')['ramp'].mean().reset_index()

    return profile

def calculate_ramp(df: pd.DataFrame):
    if df.empty:
        return None

    df_sorted = df.sort_values(['date', 'block_no']).copy()

    # Calculate ramp per day
    df_sorted['ramp'] = df_sorted.groupby('date')['demand_energy'].diff()

    return df_sorted

def calculate_ramp(df: pd.DataFrame):
    if df.empty:
        return None

    df_sorted = df.sort_values(['date', 'block_no']).copy()

    # Calculate ramp per day
    df_sorted['ramp'] = df_sorted.groupby('date')['demand_energy'].diff()

    return df_sorted


import plotly.express as px

def plot_ramp_trend(df: pd.DataFrame):
    profile = get_ramp_profile(df)

    if profile is None:
        return None

    fig = px.line(
        profile,
        x='block_no',
        y='ramp',
        title='Intraday Ramp Pattern (Demand Change per Block)',
        labels={'ramp': 'Ramp (MW/block)', 'block_no': 'Time Block'},
        markers=True
    )

    fig.update_layout(template='plotly_white')

    return fig


def generate_ramp_insights(df: pd.DataFrame):
    df_ramp = calculate_ramp(df)

    max_ramp_up = df_ramp['ramp'].max()
    max_ramp_down = df_ramp['ramp'].min()

    max_up_block = df_ramp.loc[df_ramp['ramp'].idxmax(), 'block_no']
    max_down_block = df_ramp.loc[df_ramp['ramp'].idxmin(), 'block_no']

    return f"""
    ⚡ Maximum ramp-up of {max_ramp_up:.0f} MW observed at block {int(max_up_block)}.

    🔻 Maximum ramp-down of {max_ramp_down:.0f} MW observed at block {int(max_down_block)}.

    ⚠️ High ramp rates indicate need for flexible generation (hydro/gas) to maintain grid stability.
    """


# Anomaly Detection

import numpy as np

def detect_anomalies(df: pd.DataFrame, threshold=3):
    if df.empty:
        return None

    df = df.copy()

    mean = df['demand_energy'].mean()
    std = df['demand_energy'].std()

    df['z_score'] = (df['demand_energy'] - mean) / std

    # Mark anomalies
    df['anomaly'] = np.abs(df['z_score']) > threshold

    return df




def plot_demand_with_anomalies(df: pd.DataFrame):
    df = df.copy()

    # 🔥 Aggregate to daily level
    df_daily = df.groupby('date')['demand_energy'].sum().reset_index()

    # Detect anomalies on daily data
    df_daily = detect_anomalies(df_daily)

    fig = px.line(
        df_daily,
        x='date',
        y='demand_energy',
        title='Daily Demand with Anomaly Detection',
        markers=True
    )

    # 🔴 Highlight anomalies
    anomalies = df_daily[df_daily['anomaly']]

    fig.add_scatter(
        x=anomalies['date'],
        y=anomalies['demand_energy'],
        mode='markers',
        marker=dict(size=10, color='red'),
        name='Anomalies'
    )

    fig.update_layout(
        template='plotly_white',
        hovermode='x unified'
    )

    return fig

def generate_anomaly_insights(df: pd.DataFrame):
    df_anomaly = detect_anomalies(df)

    anomalies = df_anomaly[df_anomaly['anomaly']]

    if anomalies.empty:
        return "✅ No significant anomalies detected. Demand pattern is stable."

    # Get top anomaly
    top = anomalies.iloc[0]

    date = pd.to_datetime(top['date']).strftime("%d %b %Y")
    block = int(top['block_no'])
    time = block_to_time(block)
    value = top['demand_energy']

    return f"""
    🚨 Anomaly detected: Demand reached {value:.0f} MW on {date} at {time} (Block {block}).

    ⚠️ Such deviations may indicate abnormal load behavior or data irregularities.
    """


# Intraday Anomaly Detection

def detect_intraday_anomalies(df: pd.DataFrame, threshold=2.5):
    if df.empty:
        return None

    df = df.copy()

    mean = df['demand_energy'].mean()
    std = df['demand_energy'].std()

    df['z_score'] = (df['demand_energy'] - mean) / std
    df['anomaly'] = df['z_score'].abs() > threshold

    return df


def plot_intraday_with_anomalies(df: pd.DataFrame):
    df_anomaly = detect_intraday_anomalies(df)

    if df_anomaly is None:
        return None

    fig = px.line(
        df_anomaly,
        x='block_no',
        y='demand_energy',
        title='Intraday Demand with Anomaly Detection',
        markers=True
    )

    # 🔴 Highlight anomalies
    anomalies = df_anomaly[df_anomaly['anomaly']]

    fig.add_scatter(
        x=anomalies['block_no'],
        y=anomalies['demand_energy'],
        mode='markers',
        marker=dict(size=10, color='red'),
        name='Anomalies'
    )

    fig.update_layout(template='plotly_white')

    return fig


def generate_intraday_anomaly_insights(df: pd.DataFrame):
    df_anomaly = detect_intraday_anomalies(df)

    anomalies = df_anomaly[df_anomaly['anomaly']]

    if anomalies.empty:
        return "✅ No intraday anomalies detected. Demand pattern is smooth."

    insights = []

    for _, row in anomalies.iterrows():
        block = int(row['block_no'])
        time = block_to_time(block)
        value = row['demand_energy']

        insights.append(
            f"🚨 Anomaly at {time} (Block {block}) – demand = {value:.0f} MW"
        )

    return "\n".join(insights[:5])  # limit to top 5


# ==========================================
# WEATHER CORRELATION CHARTS
# ==========================================
from plotly.subplots import make_subplots

def plot_intraday_weather_correlation(df: pd.DataFrame, date_selected, zone='WZ', param='temperature'):
    if df.empty:
        return None
        
    df_date = df[df['date'].dt.date == date_selected].copy()
    if df_date.empty:
        return None
    
    demand_col = f"{zone}_Demand"
    weather_col = f"{zone}_{param}"
    
    # Sort blocks
    if 'block_no' in df_date.columns:
        df_date = df_date.sort_values('block_no')
        x_col = 'block_no'
        x_label = 'Time Block'
    else:
        # if only one daily record exists, Intraday makes no sense. Fallback to scatter line
        x_col = 'date'
        x_label = 'Date'
        df_date = df.sort_values('date')

    if demand_col not in df_date.columns or weather_col not in df_date.columns:
        # Fallback to general demand and general parameter if regional not found
        if 'demand_energy' in df_date.columns: demand_col = 'demand_energy'
        if param in df_date.columns: weather_col = param
    
    if demand_col not in df_date.columns or weather_col not in df_date.columns:
        return None  # Missing data
        
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Plot Demand
    fig.add_trace(
        go.Scatter(x=df_date[x_col], y=df_date[demand_col], name=f"{zone} Demand", line=dict(color='blue', width=2)),
        secondary_y=False,
    )
    
    # Plot Weather
    fig.add_trace(
        go.Scatter(x=df_date[x_col], y=df_date[weather_col], name=f"{zone} {param.title()}", line=dict(color='orange', width=2, dash='dot')),
        secondary_y=True,
    )
    
    fig.update_layout(
        title=f"Intraday Demand vs {param.title()} Correlation ({zone} - {date_selected})",
        template='plotly_white',
        hovermode="x unified"
    )
    fig.update_yaxes(title_text=f"{zone} Demand (MW)", secondary_y=False, color='blue')
    fig.update_yaxes(title_text=f"{param.title()}", secondary_y=True, color='orange')
    
    return fig

def plot_regional_weather_scatter(df: pd.DataFrame, zone='WZ', param='temperature'):
    """Scatter plot: Demand on Y, Weather on X"""
    if df.empty:
        return None
        
    demand_col = f"{zone}_Demand"
    weather_col = f"{zone}_{param}"
    
    # Aggregate to daily to prevent block overplotting
    if 'date' in df.columns and demand_col in df.columns and weather_col in df.columns:
        agg_args = {demand_col: 'mean', weather_col: 'mean'}
        if 'is_weekend' in df.columns: agg_args['is_weekend'] = 'first'
        if 'is_holiday' in df.columns: agg_args['is_holiday'] = 'first'
        if 'is_special_event' in df.columns: agg_args['is_special_event'] = 'first'
        
        df_daily = df.groupby('date').agg(agg_args).reset_index()
        
        # Determine day categorization for color mapping
        if 'is_weekend' in df_daily.columns:
            def categorize_day(row):
                if row.get('is_special_event'): return 'Special Event'
                if row.get('is_holiday'): return 'Holiday'
                if row.get('is_weekend'): return 'Weekend'
                return 'Regular Workday'
            df_daily['Day Type'] = df_daily.apply(categorize_day, axis=1)
            color_arg = 'Day Type'
            color_map = {'Regular Workday': '#1C3144', 'Weekend': '#D00000', 'Holiday': '#FFBA08', 'Special Event': '#A2AEBB'}
        else:
            color_arg = demand_col
            color_map = None
    else:
        # Try finding general ones if zone specific mapping failed
        if 'demand_energy' in df.columns: demand_col = 'demand_energy'
        if param in df.columns: weather_col = param
        if demand_col in df.columns and weather_col in df.columns:
            df_daily = df.groupby('date')[[demand_col, weather_col]].mean().reset_index()
            color_arg = demand_col
            color_map = None
        else:
            return None

    if df_daily.empty or demand_col not in df_daily.columns or weather_col not in df_daily.columns:
        return None

    if color_arg == 'Day Type':
        fig = px.scatter(
            df_daily, x=weather_col, y=demand_col, trendline='ols', 
            title=f"{zone} Demand Elasticity to {param.title()}",
            labels={weather_col: f"{param.title()}", demand_col: f"{zone} Demand (MW)"},
            opacity=0.75, color='Day Type', color_discrete_map=color_map, symbol='Day Type'
        )
    else:
        fig = px.scatter(
            df_daily, x=weather_col, y=demand_col, trendline='ols',
            title=f"{zone} Demand Elasticity to {param.title()}",
            labels={weather_col: f"{param.title()}", demand_col: f"{zone} Demand (MW)"},
            opacity=0.6, color=demand_col, color_continuous_scale='Turbo'
        )
        
    fig.update_layout(template='plotly_white')
    return fig

def plot_weather_heatmap(df: pd.DataFrame, zone='WZ'):
    """Heatmap showing avg demand by weather condition (wxPhrase) and time segment (Morning, Peak, Night)"""
    if df.empty:
        return None
        
    demand_col = f"{zone}_Demand"
    wx_col = f"{zone}_wxPhraseShort"
    
    # Fallback to generic
    if demand_col not in df.columns: demand_col = 'demand_energy'
    if wx_col not in df.columns: wx_col = 'wxPhraseShort'
    
    if demand_col not in df.columns or wx_col not in df.columns:
        return None
        
    df_copy = df.copy()
    
    # Create simple time-of-day categories if blocks exist
    if 'block_no' in df_copy.columns:
        # 1-32: Night (00:00 - 08:00)
        # 33-68: Day (08:00 - 17:00)
        # 69-96: EveningPeak (17:00 - 24:00)
        df_copy['Time Segment'] = pd.cut(df_copy['block_no'], bins=[0, 32, 68, 96], labels=['Night', 'Day', 'Evening Peak'])
    else:
        df_copy['Time Segment'] = 'Daily Avg'
        
    # Standardize string condition
    df_copy[wx_col] = df_copy[wx_col].astype(str).fillna("Unknown")
    
    heat_data = df_copy.groupby(['Time Segment', wx_col])[demand_col].mean().reset_index()
    
    fig = px.density_heatmap(
        heat_data, 
        x='Time Segment', 
        y=wx_col, 
        z=demand_col, 
        histfunc='avg',
        title=f"{zone} Average Demand by Weather Condition",
        labels={'Time Segment': 'Time of Day', wx_col: 'Weather Condition', demand_col: 'Avg Demand (MW)'},
        color_continuous_scale='Viridis'
    )
    fig.update_layout(template='plotly_white')
    return fig
