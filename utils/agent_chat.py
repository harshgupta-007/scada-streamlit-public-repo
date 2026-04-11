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

    model_prompt = f"""
You are a professional SCADA analytics assistant for a public demo dashboard.

Rules:
- Use only the SCADA sample dataset context provided below.
- Do not claim access to live systems, private databases, secrets, or hidden files.
- If a question requires data not present in the context, say what is missing.
- Keep answers concise, engineering-focused, and suitable for power-system stakeholders.
- Use MW for power and GWh for energy.

Dataset context:
{data_context}

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
