import os
import pandas as pd
import re
import streamlit as st
import uuid
from typing import Dict, List, Optional

try:
    from langsmith import Client, trace, traceable, tracing_context
    LANGSMITH_AVAILABLE = True
except Exception:
    Client = None
    LANGSMITH_AVAILABLE = False
    trace = None

    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    class tracing_context:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False


DEFAULT_MODEL = "gemini-2.5-flash"
WEATHER_COLUMNS = {
    "temperature_2m": "temperature",
    "relativehumidity_2m": "relative humidity",
    "windspeed_10m": "wind speed",
    "apparent_temperature": "apparent temperature",
    "precipitation": "precipitation",
}
MONTH_LOOKUP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def get_google_api_key() -> Optional[str]:
    """Read the Google API key from Streamlit secrets without exposing it."""
    try:
        return st.secrets.get("GOOGLE_API_KEY")
    except Exception:
        return None


def is_agent_chat_configured() -> bool:
    return bool(get_google_api_key())


def get_langsmith_settings() -> Dict[str, str]:
    """Read LangSmith settings from Streamlit secrets without exposing them."""
    try:
        return {
            "api_key": st.secrets.get("LANGSMITH_API_KEY", ""),
            "project": st.secrets.get("LANGSMITH_PROJECT", "scada-streamlit-public"),
            "tracing": str(st.secrets.get("LANGSMITH_TRACING", "true")).lower(),
            "endpoint": st.secrets.get("LANGSMITH_ENDPOINT", ""),
        }
    except Exception:
        return {
            "api_key": "",
            "project": "scada-streamlit-public",
            "tracing": "false",
            "endpoint": "",
        }


def is_langsmith_configured() -> bool:
    settings = get_langsmith_settings()
    return LANGSMITH_AVAILABLE and bool(settings["api_key"])


def _build_langsmith_client():
    settings = get_langsmith_settings()
    if not LANGSMITH_AVAILABLE or not settings["api_key"]:
        return None

    client_kwargs = {"api_key": settings["api_key"]}
    if settings["endpoint"]:
        client_kwargs["api_url"] = settings["endpoint"]
    return Client(**client_kwargs)


def _configure_langsmith_environment() -> Dict[str, str]:
    settings = get_langsmith_settings()
    if not settings["api_key"]:
        return settings

    os.environ["LANGSMITH_API_KEY"] = settings["api_key"]
    os.environ["LANGSMITH_PROJECT"] = settings["project"]
    os.environ["LANGSMITH_TRACING"] = settings["tracing"]
    if settings["endpoint"]:
        os.environ["LANGSMITH_ENDPOINT"] = settings["endpoint"]
    return settings


def classify_prompt(prompt: str) -> str:
    prompt_lower = prompt.lower()
    if any(word in prompt_lower for word in ["compare", "versus", "vs", "difference", "between"]):
        return "comparison"
    if any(word in prompt_lower for word in ["intraday", "block", "selected day", "single day", "96"]):
        return "intraday"
    if any(word in prompt_lower for word in ["anomaly", "outlier", "spike", "abnormal"]):
        return "anomaly"
    if any(word in prompt_lower for word in ["weather", "temperature", "humidity", "wind", "rain", "precipitation"]):
        return "weather"
    if any(word in prompt_lower for word in ["region", "regional", "cz", "ez", "wz"]):
        return "regional"
    return "general"


def build_scada_context(df: pd.DataFrame) -> str:
    """Create a compact dataset summary for the chat model."""
    if df is None or df.empty:
        return "No SCADA data is currently selected."

    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])

    total_energy_gwh = (working_df["demand_energy"].sum() * 0.25) / 1000
    peak_row = working_df.loc[working_df["demand_energy"].idxmax()]
    min_row = working_df.loc[working_df["demand_energy"].idxmin()]
    avg_demand = working_df["demand_energy"].mean()

    def block_to_time(block_no):
        minutes = (int(block_no) - 1) * 15
        return f"{minutes // 60:02d}:{minutes % 60:02d}"

    context_lines = [
        "SCADA sample dataset context:",
        f"- Date range: {working_df['date'].min().date()} to {working_df['date'].max().date()}",
        f"- Rows selected: {len(working_df):,}",
        f"- Total energy: {total_energy_gwh:,.1f} GWh",
        f"- Average demand: {avg_demand:,.0f} MW",
        (
            "- Peak demand: "
            f"{peak_row['demand_energy']:,.0f} MW on {peak_row['date'].date()} "
            f"at {block_to_time(peak_row['block_no'])}"
        ),
        (
            "- Minimum demand: "
            f"{min_row['demand_energy']:,.0f} MW on {min_row['date'].date()} "
            f"at {block_to_time(min_row['block_no'])}"
        ),
    ]

    region_cols = ["CZ_Demand", "EZ_Demand", "WZ_Demand"]
    if all(col in working_df.columns for col in region_cols):
        regional_totals = working_df[region_cols].sum()
        context_lines.append(
            "- Regional demand totals: "
            + ", ".join(f"{col.replace('_Demand', '')}={value:,.0f} MW-blocks" for col, value in regional_totals.items())
        )

    gen_cols = ["thermal_gen", "hydel_gen", "renewable_gen"]
    if all(col in working_df.columns for col in gen_cols):
        generation_gwh = working_df[gen_cols].sum() * 0.25 / 1000
        context_lines.append(
            "- Generation mix: "
            + ", ".join(f"{col.replace('_gen', '').title()}={value:,.1f} GWh" for col, value in generation_gwh.items())
        )

    available_weather_cols = [col for col in WEATHER_COLUMNS if col in working_df.columns]
    if available_weather_cols:
        context_lines.append(
            "- Weather variables available: "
            + ", ".join(WEATHER_COLUMNS[col] for col in available_weather_cols)
        )

    return "\n".join(context_lines)


def _dataset_default_year_month(df: pd.DataFrame) -> tuple[int, int]:
    dates = pd.to_datetime(df["date"])
    return int(dates.dt.year.mode().iloc[0]), int(dates.dt.month.mode().iloc[0])


def _parse_user_dates(prompt: str, df: pd.DataFrame) -> List[pd.Timestamp]:
    """Parse common user date references without external services."""
    prompt_lower = prompt.lower()
    default_year, default_month = _dataset_default_year_month(df)
    parsed_dates = []

    for match in re.finditer(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", prompt_lower):
        year, month, day = map(int, match.groups())
        parsed_dates.append(pd.Timestamp(year=year, month=month, day=day))

    month_names = "|".join(MONTH_LOOKUP.keys())
    date_patterns = [
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_names})(?:\s+(20\d{{2}}))?\b",
        rf"\b({month_names})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s+(20\d{{2}}))?\b",
    ]

    for match in re.finditer(date_patterns[0], prompt_lower):
        day = int(match.group(1))
        month = MONTH_LOOKUP[match.group(2)]
        year = int(match.group(3)) if match.group(3) else default_year
        parsed_dates.append(pd.Timestamp(year=year, month=month, day=day))

    for match in re.finditer(date_patterns[1], prompt_lower):
        month = MONTH_LOOKUP[match.group(1)]
        day = int(match.group(2))
        year = int(match.group(3)) if match.group(3) else default_year
        parsed_dates.append(pd.Timestamp(year=year, month=month, day=day))

    if re.search(r"\bintraday\b|\bblock\b|\bsingle day\b|\bselected day\b", prompt_lower):
        for match in re.finditer(r"\b([1-9]|[12]\d|3[01])(?:st|nd|rd|th)?\b", prompt_lower):
            day = int(match.group(1))
            try:
                parsed_dates.append(pd.Timestamp(year=default_year, month=default_month, day=day))
            except ValueError:
                pass

    unique_dates = []
    seen = set()
    for parsed_date in parsed_dates:
        key = parsed_date.date()
        if key not in seen:
            seen.add(key)
            unique_dates.append(parsed_date)
    return unique_dates


def _parse_user_month(prompt: str, df: pd.DataFrame) -> Optional[tuple[int, int]]:
    prompt_lower = prompt.lower()
    default_year, _ = _dataset_default_year_month(df)

    month_names = "|".join(MONTH_LOOKUP.keys())
    match = re.search(rf"\b({month_names})(?:\s+(20\d{{2}}))?\b", prompt_lower)
    if not match:
        return None

    month = MONTH_LOOKUP[match.group(1)]
    year = int(match.group(2)) if match.group(2) else default_year
    return year, month


def resolve_analysis_scope(prompt: str, df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Filter data to dates mentioned in the prompt when possible."""
    if df is None or df.empty:
        return df, "Analysis scope: no data available."

    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])
    requested_dates = _parse_user_dates(prompt, working_df)

    if not requested_dates:
        requested_month = _parse_user_month(prompt, working_df)
        if requested_month:
            year, month = requested_month
            month_df = working_df[(working_df["date"].dt.year == year) & (working_df["date"].dt.month == month)]
            if not month_df.empty:
                return month_df, f"Analysis scope: user-requested month: {year}-{month:02d}."

        min_date = working_df["date"].min().date()
        max_date = working_df["date"].max().date()
        return working_df, f"Analysis scope: selected sidebar range ({min_date} to {max_date})."

    available_dates = set(working_df["date"].dt.date)
    matched_dates = [date for date in requested_dates if date.date() in available_dates]
    missing_dates = [date.date().isoformat() for date in requested_dates if date.date() not in available_dates]

    if not matched_dates:
        min_date = working_df["date"].min().date()
        max_date = working_df["date"].max().date()
        return (
            working_df,
            "Analysis scope: selected sidebar range "
            f"({min_date} to {max_date}); requested date(s) not found in that range: {', '.join(missing_dates)}.",
        )

    filtered_df = working_df[working_df["date"].dt.date.isin([date.date() for date in matched_dates])]
    matched_text = ", ".join(date.date().isoformat() for date in matched_dates)
    scope_text = f"Analysis scope: user-requested date(s): {matched_text}."
    if missing_dates:
        scope_text += f" Missing date(s) in selected data: {', '.join(missing_dates)}."
    return filtered_df, scope_text


def tool_compare_dates(prompt: str, df: pd.DataFrame) -> str:
    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])
    dates = _parse_user_dates(prompt, working_df)
    matched_dates = [date for date in dates if date.date() in set(working_df["date"].dt.date)]

    if len(matched_dates) < 2:
        return "Tool: compare_dates\n- At least two available dates are required for comparison."

    lines = ["Tool: compare_dates"]
    summaries = []
    for date in matched_dates[:2]:
        day_df = working_df[working_df["date"].dt.date == date.date()]
        energy_gwh = (day_df["demand_energy"].sum() * 0.25) / 1000
        peak_row = day_df.loc[day_df["demand_energy"].idxmax()]
        summary = {
            "date": date.date().isoformat(),
            "energy_gwh": energy_gwh,
            "avg_mw": day_df["demand_energy"].mean(),
            "peak_mw": peak_row["demand_energy"],
            "peak_time": _block_to_time(peak_row["block_no"]),
        }
        summaries.append(summary)
        lines.append(
            f"- {summary['date']}: energy={summary['energy_gwh']:,.1f} GWh, "
            f"avg={summary['avg_mw']:,.0f} MW, peak={summary['peak_mw']:,.0f} MW at {summary['peak_time']}"
        )
        weather_parts = []
        for col, label in WEATHER_COLUMNS.items():
            if col in day_df.columns:
                weather_parts.append(f"{label}={day_df[col].mean():,.1f}")
        if weather_parts:
            lines.append("- Weather average: " + ", ".join(weather_parts))

    first, second = summaries[0], summaries[1]
    lines.append(
        f"- Difference ({second['date']} minus {first['date']}): "
        f"energy={second['energy_gwh'] - first['energy_gwh']:,.1f} GWh, "
        f"avg={second['avg_mw'] - first['avg_mw']:,.0f} MW, "
        f"peak={second['peak_mw'] - first['peak_mw']:,.0f} MW"
    )
    return "\n".join(lines)


def _block_to_time(block_no) -> str:
    minutes = (int(block_no) - 1) * 15
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def tool_summary(df: pd.DataFrame) -> str:
    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])
    total_energy_gwh = (working_df["demand_energy"].sum() * 0.25) / 1000
    return "\n".join(
        [
            "Tool: summary",
            f"- Date range: {working_df['date'].min().date()} to {working_df['date'].max().date()}",
            f"- Records: {len(working_df):,}",
            f"- Total energy: {total_energy_gwh:,.1f} GWh",
            f"- Average demand: {working_df['demand_energy'].mean():,.0f} MW",
            f"- Peak demand: {working_df['demand_energy'].max():,.0f} MW",
            f"- Minimum demand: {working_df['demand_energy'].min():,.0f} MW",
        ]
    )


def tool_peak_and_minimum(df: pd.DataFrame) -> str:
    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])
    peak_row = working_df.loc[working_df["demand_energy"].idxmax()]
    min_row = working_df.loc[working_df["demand_energy"].idxmin()]
    return "\n".join(
        [
            "Tool: peak_and_minimum",
            (
                f"- Peak: {peak_row['demand_energy']:,.0f} MW on {peak_row['date'].date()} "
                f"at {_block_to_time(peak_row['block_no'])} (Block {int(peak_row['block_no'])})"
            ),
            (
                f"- Minimum: {min_row['demand_energy']:,.0f} MW on {min_row['date'].date()} "
                f"at {_block_to_time(min_row['block_no'])} (Block {int(min_row['block_no'])})"
            ),
        ]
    )


def tool_regional_contribution(df: pd.DataFrame) -> str:
    region_cols = ["CZ_Demand", "EZ_Demand", "WZ_Demand"]
    if not all(col in df.columns for col in region_cols):
        return "Tool: regional_contribution\n- Regional columns are not available."

    totals = df[region_cols].sum()
    total_demand = df["demand_energy"].sum()
    lines = ["Tool: regional_contribution"]
    for col in region_cols:
        pct = (totals[col] / total_demand) * 100 if total_demand else 0
        lines.append(f"- {col.replace('_Demand', '')}: {pct:.1f}% contribution")
    lines.append(f"- Dominant region: {totals.idxmax().replace('_Demand', '')}")
    return "\n".join(lines)


def tool_generation_mix(df: pd.DataFrame) -> str:
    gen_cols = ["thermal_gen", "hydel_gen", "renewable_gen"]
    if not all(col in df.columns for col in gen_cols):
        return "Tool: generation_mix\n- Generation columns are not available."

    generation_gwh = df[gen_cols].sum() * 0.25 / 1000
    total_gwh = generation_gwh.sum()
    lines = ["Tool: generation_mix"]
    for col in gen_cols:
        pct = (generation_gwh[col] / total_gwh) * 100 if total_gwh else 0
        label = col.replace("_gen", "").title()
        lines.append(f"- {label}: {generation_gwh[col]:,.1f} GWh ({pct:.1f}%)")
    return "\n".join(lines)


def tool_ramp_analysis(df: pd.DataFrame) -> str:
    working_df = df.sort_values(["date", "block_no"]).copy()
    working_df["ramp"] = working_df.groupby("date")["demand_energy"].diff()
    ramp_df = working_df.dropna(subset=["ramp"])
    if ramp_df.empty:
        return "Tool: ramp_analysis\n- Not enough data to calculate ramps."

    max_up = ramp_df.loc[ramp_df["ramp"].idxmax()]
    max_down = ramp_df.loc[ramp_df["ramp"].idxmin()]
    return "\n".join(
        [
            "Tool: ramp_analysis",
            (
                f"- Maximum ramp-up: {max_up['ramp']:,.0f} MW/block on "
                f"{pd.to_datetime(max_up['date']).date()} at {_block_to_time(max_up['block_no'])}"
            ),
            (
                f"- Maximum ramp-down: {max_down['ramp']:,.0f} MW/block on "
                f"{pd.to_datetime(max_down['date']).date()} at {_block_to_time(max_down['block_no'])}"
            ),
        ]
    )


def tool_anomaly_scan(df: pd.DataFrame) -> str:
    working_df = df.copy()
    std = working_df["demand_energy"].std()
    if not std:
        return "Tool: anomaly_scan\n- No demand variation available for anomaly scoring."

    working_df["z_score"] = (working_df["demand_energy"] - working_df["demand_energy"].mean()) / std
    anomalies = working_df[working_df["z_score"].abs() > 3].copy()
    if anomalies.empty:
        return "Tool: anomaly_scan\n- No demand points exceeded the z-score threshold of 3."

    anomalies["abs_z"] = anomalies["z_score"].abs()
    top = anomalies.sort_values("abs_z", ascending=False).head(5)
    lines = ["Tool: anomaly_scan", f"- Anomalies found: {len(anomalies):,}"]
    for _, row in top.iterrows():
        lines.append(
            f"- {pd.to_datetime(row['date']).date()} {_block_to_time(row['block_no'])}: "
            f"{row['demand_energy']:,.0f} MW (z={row['z_score']:.2f})"
        )
    return "\n".join(lines)


def _available_weather_columns(df: pd.DataFrame) -> List[str]:
    return [col for col in WEATHER_COLUMNS if col in df.columns]


def _preferred_weather_column(prompt: str, df: pd.DataFrame) -> Optional[str]:
    available_cols = _available_weather_columns(df)
    if not available_cols:
        return None

    prompt_lower = prompt.lower()
    keyword_map = {
        "temperature_2m": ["temperature", "temp", "heat", "hot", "cool"],
        "apparent_temperature": ["apparent", "feels like", "felt"],
        "relativehumidity_2m": ["humidity", "humid"],
        "windspeed_10m": ["wind", "wind speed"],
        "precipitation": ["rain", "precipitation", "precip"],
    }
    for col, keywords in keyword_map.items():
        if col in available_cols and any(keyword in prompt_lower for keyword in keywords):
            return col
    return available_cols[0]


def tool_weather_summary(df: pd.DataFrame) -> str:
    weather_cols = _available_weather_columns(df)
    if not weather_cols:
        return "Tool: weather_summary\n- Weather columns are not available in the selected data."

    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])
    lines = ["Tool: weather_summary"]
    for col in weather_cols:
        valid_df = working_df[["demand_energy", col]].dropna()
        if valid_df.empty:
            continue
        corr = valid_df["demand_energy"].corr(valid_df[col]) if len(valid_df) > 1 else 0
        corr = 0 if pd.isna(corr) else corr
        lines.append(
            f"- {WEATHER_COLUMNS[col]}: avg={valid_df[col].mean():,.1f}, "
            f"min={valid_df[col].min():,.1f}, max={valid_df[col].max():,.1f}, "
            f"demand correlation={corr:.2f}"
        )
    return "\n".join(lines)


def tool_weather_extremes(df: pd.DataFrame, prompt: str) -> str:
    weather_col = _preferred_weather_column(prompt, df)
    if not weather_col:
        return "Tool: weather_extremes\n- Weather columns are not available in the selected data."

    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])
    valid_df = working_df[["date", "block_no", "demand_energy", weather_col]].dropna()
    if valid_df.empty:
        return "Tool: weather_extremes\n- No overlapping demand and weather records are available."

    hottest = valid_df.loc[valid_df[weather_col].idxmax()]
    coolest = valid_df.loc[valid_df[weather_col].idxmin()]
    daily_df = valid_df.groupby("date")[["demand_energy", weather_col]].mean().reset_index()
    high_weather_day = daily_df.loc[daily_df[weather_col].idxmax()]
    high_demand_day = daily_df.loc[daily_df["demand_energy"].idxmax()]
    label = WEATHER_COLUMNS[weather_col]

    return "\n".join(
        [
            "Tool: weather_extremes",
            (
                f"- Highest block {label}: {hottest[weather_col]:,.1f} on "
                f"{hottest['date'].date()} at {_block_to_time(hottest['block_no'])}; "
                f"demand was {hottest['demand_energy']:,.0f} MW"
            ),
            (
                f"- Lowest block {label}: {coolest[weather_col]:,.1f} on "
                f"{coolest['date'].date()} at {_block_to_time(coolest['block_no'])}; "
                f"demand was {coolest['demand_energy']:,.0f} MW"
            ),
            (
                f"- Highest average {label} day: {high_weather_day['date'].date()} "
                f"({high_weather_day[weather_col]:,.1f}); avg demand was "
                f"{high_weather_day['demand_energy']:,.0f} MW"
            ),
            (
                f"- Highest average demand day: {high_demand_day['date'].date()} "
                f"({high_demand_day['demand_energy']:,.0f} MW); avg {label} was "
                f"{high_demand_day[weather_col]:,.1f}"
            ),
        ]
    )


def tool_weather_intraday(df: pd.DataFrame, prompt: str) -> str:
    weather_col = _preferred_weather_column(prompt, df)
    if not weather_col:
        return "Tool: weather_intraday\n- Weather columns are not available in the selected data."

    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])
    valid_df = working_df[["date", "block_no", "demand_energy", weather_col]].dropna()
    if valid_df.empty:
        return "Tool: weather_intraday\n- No overlapping intraday demand and weather records are available."

    if valid_df["date"].dt.date.nunique() > 1:
        latest_date = valid_df["date"].max().date()
        valid_df = valid_df[valid_df["date"].dt.date == latest_date]

    peak = valid_df.loc[valid_df["demand_energy"].idxmax()]
    minimum = valid_df.loc[valid_df["demand_energy"].idxmin()]
    weather_high = valid_df.loc[valid_df[weather_col].idxmax()]
    corr = valid_df["demand_energy"].corr(valid_df[weather_col]) if len(valid_df) > 1 else 0
    corr = 0 if pd.isna(corr) else corr
    label = WEATHER_COLUMNS[weather_col]

    return "\n".join(
        [
            "Tool: weather_intraday",
            f"- Date analyzed: {valid_df['date'].iloc[0].date()}",
            (
                f"- Demand peak: {peak['demand_energy']:,.0f} MW at "
                f"{_block_to_time(peak['block_no'])}; {label} was {peak[weather_col]:,.1f}"
            ),
            (
                f"- Demand minimum: {minimum['demand_energy']:,.0f} MW at "
                f"{_block_to_time(minimum['block_no'])}; {label} was {minimum[weather_col]:,.1f}"
            ),
            (
                f"- Highest {label}: {weather_high[weather_col]:,.1f} at "
                f"{_block_to_time(weather_high['block_no'])}; demand was {weather_high['demand_energy']:,.0f} MW"
            ),
            f"- Block-level demand correlation with {label}: {corr:.2f}",
        ]
    )


def run_relevant_tools(prompt: str, df: pd.DataFrame) -> str:
    """Run deterministic local dataframe tools based on the user question."""
    prompt_lower = prompt.lower()
    tools = []
    scoped_df, scope_text = resolve_analysis_scope(prompt, df)
    weather_requested = any(
        word in prompt_lower
        for word in [
            "weather",
            "temperature",
            "temp",
            "humidity",
            "wind",
            "rain",
            "precipitation",
            "apparent",
            "heat",
        ]
    )

    if any(word in prompt_lower for word in ["compare", "comparison", "versus", "vs", "difference", "between"]):
        tools.append(lambda _: tool_compare_dates(prompt, df))
    if any(word in prompt_lower for word in ["summary", "overview", "total", "average"]):
        tools.append(tool_summary)
    if any(word in prompt_lower for word in ["peak", "minimum", "min", "maximum", "max"]):
        tools.append(tool_peak_and_minimum)
    if any(word in prompt_lower for word in ["region", "regional", "cz", "ez", "wz", "contribution"]):
        tools.append(tool_regional_contribution)
    if any(word in prompt_lower for word in ["generation", "thermal", "hydel", "renewable", "solar", "wind"]):
        tools.append(tool_generation_mix)
    if any(word in prompt_lower for word in ["ramp", "ramping", "rise", "drop", "change"]):
        tools.append(tool_ramp_analysis)
    if any(word in prompt_lower for word in ["anomaly", "anomalies", "spike", "outlier", "abnormal"]):
        tools.append(tool_anomaly_scan)
    if weather_requested:
        tools.append(tool_weather_summary)
    if weather_requested and any(word in prompt_lower for word in ["highest", "lowest", "maximum", "minimum", "max", "min", "peak"]):
        tools.append(lambda data: tool_weather_extremes(data, prompt))
    if weather_requested and any(word in prompt_lower for word in ["intraday", "block", "selected day", "single day", "96"]):
        tools.append(lambda data: tool_weather_intraday(data, prompt))

    if not tools:
        tools = [tool_summary, tool_peak_and_minimum, tool_regional_contribution]
        if _available_weather_columns(scoped_df):
            tools.append(tool_weather_summary)

    return scope_text + "\n\n" + "\n\n".join(tool(scoped_df) for tool in tools)


@traceable(run_type="tool", name="Deterministic Data Tools")
def _run_tool_context(prompt: str, df: pd.DataFrame) -> str:
    return run_relevant_tools(prompt, df)


@traceable(run_type="llm", name="Gemini Agent Response")
def _generate_gemini_response(model_name: str, model_prompt: str) -> str:
    from google import genai

    client = genai.Client(api_key=get_google_api_key())
    response = client.models.generate_content(
        model=model_name,
        contents=model_prompt,
    )
    return response.text or "I could not generate a response for that question."


@traceable(run_type="chain", name="SCADA Agent Chat")
def _run_agent_chat(prompt: str, df: pd.DataFrame, history: Optional[List[Dict[str, str]]] = None) -> str:
    """Build agent context and request an answer from Gemini."""
    api_key = get_google_api_key()
    if not api_key:
        return "Agent Chat is not configured. Add GOOGLE_API_KEY in Streamlit secrets to enable it."

    try:
        from google import genai  # noqa: F401
    except Exception:
        return "The google-genai package is not installed. Check requirements.txt and redeploy the app."

    history = history or []
    compact_history = history[-6:]
    history_text = "\n".join(f"{item['role']}: {item['content']}" for item in compact_history)
    scoped_df, scope_text = resolve_analysis_scope(prompt, df)
    data_context = scope_text + "\n" + build_scada_context(scoped_df)
    tool_context = _run_tool_context(prompt, df)

    model_prompt = f"""
You are a professional SCADA analytics assistant for a public demo dashboard.

Rules:
- Use only the public SCADA and weather sample dataset context provided below.
- Do not claim access to live systems, private databases, secrets, or hidden files.
- If a question requires data not present in the context, say what is missing.
- Keep answers concise, engineering-focused, and suitable for power-system stakeholders.
- Use MW for power and GWh for energy.
- Weather data is public Open-Meteo sample data merged by date and 15-minute block.
- Prefer the deterministic tool results over general reasoning when answering numerical questions.
- If the user mentions a date, use the analysis scope and tool results for that date when available.

Dataset context:
{data_context}

Deterministic local tool results:
{tool_context}

Recent chat history:
{history_text if history_text else "No prior chat history."}

User question:
{prompt}
"""

    try:
        return _generate_gemini_response(DEFAULT_MODEL, model_prompt)
    except Exception as exc:
        return f"Agent response failed: {exc}"


def ask_scada_agent(prompt: str, df: pd.DataFrame, history: Optional[List[Dict[str, str]]] = None) -> str:
    """Ask Gemini to answer using only the selected public SCADA/weather sample data."""
    result = ask_scada_agent_with_trace(prompt, df, history)
    return result["response"]


def ask_scada_agent_with_trace(
    prompt: str,
    df: pd.DataFrame,
    history: Optional[List[Dict[str, str]]] = None,
    trace_metadata: Optional[Dict[str, object]] = None,
) -> Dict[str, Optional[str]]:
    """Return the agent response along with the root LangSmith trace id when enabled."""
    settings = _configure_langsmith_environment()
    tracing_enabled = settings["tracing"] == "true" and bool(settings["api_key"]) and LANGSMITH_AVAILABLE
    client = _build_langsmith_client() if tracing_enabled else None

    metadata = {
        "app": "scada-streamlit-public",
        "model": DEFAULT_MODEL,
        "rows_selected": int(len(df)) if df is not None else 0,
        "weather_enabled": bool(df is not None and any(col in df.columns for col in WEATHER_COLUMNS)),
        "prompt_type": classify_prompt(prompt),
    }
    if trace_metadata:
        metadata.update(trace_metadata)

    if tracing_enabled and trace is not None:
        with tracing_context(
            enabled=tracing_enabled,
            client=client,
            project_name=settings["project"],
            tags=["streamlit", "agent-chat", "public-demo"],
            metadata=metadata,
        ):
            with trace(
                name="SCADA Agent Chat Session",
                run_type="chain",
                inputs={"prompt": prompt, "history_length": len(history or [])},
                metadata=metadata,
                tags=["streamlit", "agent-chat", "public-demo"],
                project_name=settings["project"],
                client=client,
            ) as root_run:
                response = _run_agent_chat(prompt, df, history)
                root_run.outputs = {"response": response}
                return {
                    "response": response,
                    "trace_id": str(root_run.id),
                    "project": settings["project"],
                }

    response = _run_agent_chat(prompt, df, history)
    return {
        "response": response,
        "trace_id": None,
        "project": settings["project"],
    }


def submit_langsmith_feedback(
    trace_id: str,
    score: float,
    comment: str = "",
    feedback_key: str = "user_helpfulness",
) -> str:
    """Submit user feedback to LangSmith for a completed trace."""
    settings = _configure_langsmith_environment()
    client = _build_langsmith_client()
    if not trace_id or not client or not settings["api_key"]:
        return "LangSmith feedback is not configured."

    try:
        uuid.UUID(str(trace_id))
    except Exception:
        return "Feedback could not be submitted because the trace id is invalid."

    try:
        client.create_feedback(
            key=feedback_key,
            score=score,
            trace_id=trace_id,
            comment=comment or None,
        )
        return "Feedback submitted to LangSmith."
    except Exception:
        return "Feedback could not be submitted to LangSmith right now."
