from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Optional

import pandas as pd
import streamlit as st

from utils.data_loader import MONGODB_DB_NAME, get_data_source_label, get_mongo_client, is_mongodb_configured


FORECAST_RUN_COLLECTION_NAME = "Forecast_run_logs"
FORECAST_MODEL_VERSION = "v1.1-weather-block-baseline"


def is_forecast_run_logging_enabled() -> bool:
    try:
        enabled = str(st.secrets.get("ENABLE_FORECAST_RUN_LOGGING", "false")).lower()
    except Exception:
        enabled = "false"
    return enabled == "true" and is_mongodb_configured()


def get_forecast_run_logging_mode() -> str:
    if is_forecast_run_logging_enabled():
        return "MongoDB persistence enabled"
    if is_mongodb_configured():
        return "Read-only mode (logging disabled)"
    return "Sample/local mode (no persistence)"


def build_forecast_run_record(
    summary: dict,
    weather_signal_label: str,
    filters: dict,
    fallback_reason: Optional[str] = None,
) -> dict:
    created_at = datetime.now(timezone.utc).isoformat()
    record = {
        "run_id": str(uuid.uuid4()),
        "created_at_utc": created_at,
        "model_version": FORECAST_MODEL_VERSION,
        "mode": summary.get("mode"),
        "target_date": str(summary.get("target_date")),
        "lookback_days": int(summary.get("lookback_days", 0)),
        "weather_signal": weather_signal_label,
        "weather_column": summary.get("weather_col"),
        "forecast_peak_mw": round(float(summary.get("forecast_peak_mw", 0.0)), 2),
        "forecast_peak_time": summary.get("forecast_peak_time"),
        "peak_window_label": summary.get("peak_window_label"),
        "forecast_avg_mw": round(float(summary.get("forecast_avg_mw", 0.0)), 2),
        "forecast_energy_gwh": round(float(summary.get("forecast_energy_gwh", 0.0)), 3),
        "actual_peak_mw": (
            round(float(summary["actual_peak_mw"]), 2)
            if summary.get("actual_peak_mw") == summary.get("actual_peak_mw")
            else None
        ),
        "actual_peak_time": summary.get("actual_peak_time"),
        "actual_energy_gwh": (
            round(float(summary["actual_energy_gwh"]), 3)
            if summary.get("actual_energy_gwh") == summary.get("actual_energy_gwh")
            else None
        ),
        "mae_mw": round(float(summary["mae_mw"]), 2) if summary.get("mae_mw") == summary.get("mae_mw") else None,
        "mape_pct": round(float(summary["mape"]) * 100, 3) if summary.get("mape") == summary.get("mape") else None,
        "overall_risk_level": summary.get("overall_risk_level"),
        "risk_flags": summary.get("risk_flags", []),
        "risk_cards": summary.get("risk_cards", []),
        "seasonality_warning": bool(summary.get("seasonality_warning", False)),
        "data_source": get_data_source_label(),
        "filters": {
            "start_date": str(filters.get("start_date", "")),
            "end_date": str(filters.get("end_date", "")),
            "exclude_weekends": bool(filters.get("exclude_weekends", False)),
            "exclude_holidays": bool(filters.get("exclude_holidays", False)),
            "exclude_events": bool(filters.get("exclude_events", False)),
        },
        "logging_mode": get_forecast_run_logging_mode(),
        "fallback_reason": fallback_reason,
    }
    return record


def persist_forecast_run_record(record: dict) -> tuple[bool, str]:
    if not is_forecast_run_logging_enabled():
        return False, "Forecast run logging is currently in safe read-only mode."

    client = get_mongo_client()
    if client is None:
        return False, "MongoDB client is unavailable for forecast run logging."

    try:
        collection = client[MONGODB_DB_NAME][FORECAST_RUN_COLLECTION_NAME]
        collection.insert_one(record.copy())
        return True, "Forecast run record stored in MongoDB."
    except Exception as exc:
        return False, f"Forecast run record could not be stored: {exc}"


def remember_forecast_run(record: dict):
    recent_runs = st.session_state.get("forecast_recent_runs", [])
    recent_runs = [record] + recent_runs
    st.session_state["forecast_recent_runs"] = recent_runs[:25]


def get_recent_session_forecast_runs() -> pd.DataFrame:
    recent_runs = st.session_state.get("forecast_recent_runs", [])
    if not recent_runs:
        return pd.DataFrame()
    df = pd.DataFrame(recent_runs)
    if "created_at_utc" in df.columns:
        df["created_at_utc"] = pd.to_datetime(df["created_at_utc"])
    return df


def load_recent_persisted_forecast_runs(limit: int = 20) -> pd.DataFrame:
    if not is_forecast_run_logging_enabled():
        return pd.DataFrame()

    client = get_mongo_client()
    if client is None:
        return pd.DataFrame()

    try:
        collection = client[MONGODB_DB_NAME][FORECAST_RUN_COLLECTION_NAME]
        records = list(
            collection.find({}, {"_id": 0})
            .sort("created_at_utc", -1)
            .limit(limit)
        )
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        if "created_at_utc" in df.columns:
            df["created_at_utc"] = pd.to_datetime(df["created_at_utc"])
        return df
    except Exception:
        return pd.DataFrame()
