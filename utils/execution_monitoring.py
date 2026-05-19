from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid
from typing import Optional

import pandas as pd

from utils.data_loader import MONGODB_DB_NAME, get_mongo_client, is_mongodb_configured
from utils.forecast_registry import is_forecast_run_logging_enabled


FORECAST_JOB_EXECUTION_COLLECTION = "Forecast_job_executions"


def build_execution_event(
    job_name: str,
    status: str,
    started_at_utc: datetime,
    ended_at_utc: Optional[datetime] = None,
    run_record: Optional[dict] = None,
    message: str = "",
    error_message: Optional[str] = None,
) -> dict:
    ended_at_utc = ended_at_utc or datetime.now(timezone.utc)
    duration_seconds = max((ended_at_utc - started_at_utc).total_seconds(), 0.0)

    record = {
        "execution_id": str(uuid.uuid4()),
        "job_name": job_name,
        "status": status,
        "started_at_utc": started_at_utc.isoformat(),
        "ended_at_utc": ended_at_utc.isoformat(),
        "duration_seconds": round(duration_seconds, 3),
        "message": message,
        "error_message": error_message,
    }
    if run_record:
        record.update(
            {
                "run_id": run_record.get("run_id"),
                "mode": run_record.get("mode"),
                "target_date": run_record.get("target_date"),
                "overall_risk_level": run_record.get("overall_risk_level"),
                "operator_headline": run_record.get("operator_headline"),
            }
        )
    return record


def persist_execution_event(record: dict) -> tuple[bool, str]:
    if not is_forecast_run_logging_enabled():
        return False, "Execution monitoring persistence is currently in safe read-only mode."
    if not is_mongodb_configured():
        return False, "MongoDB is not configured for execution monitoring persistence."

    client = get_mongo_client()
    if client is None:
        return False, "MongoDB client is unavailable for execution monitoring persistence."

    try:
        collection = client[MONGODB_DB_NAME][FORECAST_JOB_EXECUTION_COLLECTION]
        collection.insert_one(record.copy())
        return True, "Execution event stored in MongoDB."
    except Exception as exc:
        return False, f"Execution event could not be stored: {exc}"


def load_recent_execution_events(limit: int = 30) -> pd.DataFrame:
    if not is_forecast_run_logging_enabled():
        return pd.DataFrame()

    client = get_mongo_client()
    if client is None:
        return pd.DataFrame()

    try:
        collection = client[MONGODB_DB_NAME][FORECAST_JOB_EXECUTION_COLLECTION]
        records = list(
            collection.find({}, {"_id": 0})
            .sort("started_at_utc", -1)
            .limit(limit)
        )
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        for col in ["started_at_utc", "ended_at_utc"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
        return df
    except Exception:
        return pd.DataFrame()


def build_execution_health_summary(events_df: pd.DataFrame, stale_hours: int = 30) -> dict:
    if events_df.empty:
        return {
            "status": "Unknown",
            "summary": "No persisted execution history is available yet.",
            "last_run_at": None,
            "last_success_at": None,
            "recent_failures": 0,
        }

    working_df = events_df.sort_values("started_at_utc", ascending=False).copy()
    latest = working_df.iloc[0]
    successes = working_df[working_df["status"] == "success"]
    failures = working_df[working_df["status"] == "failure"]

    last_run_at = latest["started_at_utc"]
    last_success_at = successes.iloc[0]["started_at_utc"] if not successes.empty else None
    stale_cutoff = pd.Timestamp.now(tz=timezone.utc) - pd.Timedelta(hours=stale_hours)
    stale = last_run_at < stale_cutoff if last_run_at is not None else True

    if latest["status"] == "failure":
        status = "High"
        summary = "The latest scheduled execution failed and needs attention."
    elif stale:
        status = "Moderate"
        summary = "The automation appears stale because no recent execution was recorded in the expected window."
    else:
        status = "Low"
        summary = "The latest scheduled execution completed successfully within the expected time window."

    return {
        "status": status,
        "summary": summary,
        "last_run_at": last_run_at,
        "last_success_at": last_success_at,
        "recent_failures": int(len(failures.head(7))),
        "latest_status": latest["status"],
    }
