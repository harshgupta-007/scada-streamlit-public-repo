import pandas as pd
import streamlit as st
from typing import Dict, List, Optional


DEFAULT_MODEL = "gemini-2.5-flash"


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

    return "\n\n".join(tool(df) for tool in tools)


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
    data_context = build_scada_context(df)
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
