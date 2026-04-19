import pandas as pd
import re
import streamlit as st
from typing import Dict, List, Optional


DEFAULT_MODEL = "gemini-2.5-flash"
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


def run_relevant_tools(prompt: str, df: pd.DataFrame) -> str:
    """Run deterministic local dataframe tools based on the user question."""
    prompt_lower = prompt.lower()
    tools = []
    scoped_df, scope_text = resolve_analysis_scope(prompt, df)

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

    if not tools:
        tools = [tool_summary, tool_peak_and_minimum, tool_regional_contribution]

    return scope_text + "\n\n" + "\n\n".join(tool(scoped_df) for tool in tools)


def ask_scada_agent(prompt: str, df: pd.DataFrame, history: Optional[List[Dict[str, str]]] = None) -> str:
    """Ask Gemini to answer using only the selected public SCADA sample data."""
    api_key = get_google_api_key()
    if not api_key:
        return "Agent Chat is not configured. Add GOOGLE_API_KEY in Streamlit secrets to enable it."

    try:
        from google import genai
    except Exception:
        return "The google-genai package is not installed. Check requirements.txt and redeploy the app."

    history = history or []
    compact_history = history[-6:]
    history_text = "\n".join(f"{item['role']}: {item['content']}" for item in compact_history)
    scoped_df, scope_text = resolve_analysis_scope(prompt, df)
    data_context = scope_text + "\n" + build_scada_context(scoped_df)
    tool_context = run_relevant_tools(prompt, df)

    model_prompt = f"""
You are a professional SCADA analytics assistant for a public demo dashboard.

Rules:
- Use only the SCADA sample dataset context provided below.
- Do not claim access to live systems, private databases, secrets, or hidden files.
- If a question requires data not present in the context, say what is missing.
- Keep answers concise, engineering-focused, and suitable for power-system stakeholders.
- Use MW for power and GWh for energy.
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
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=model_prompt,
        )
        return response.text or "I could not generate a response for that question."
    except Exception as exc:
        return f"Agent response failed: {exc}"
