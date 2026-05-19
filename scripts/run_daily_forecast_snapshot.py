import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.forecast_registry import (
    get_forecast_run_logging_mode,
    persist_briefing_snapshot,
    persist_forecast_run_record,
)
from utils.execution_monitoring import build_execution_event, persist_execution_event
from utils.forecast_snapshot import generate_daily_snapshot


def main():
    parser = argparse.ArgumentParser(description="Generate and optionally persist a daily forecast snapshot.")
    parser.add_argument("--weather-signal", default="Apparent Temperature")
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--prefer-forward", action="store_true")
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()

    started_at = datetime.now(timezone.utc)
    try:
        snapshot = generate_daily_snapshot(
            weather_signal_label=args.weather_signal,
            lookback_days=args.lookback_days,
            filters={},
            prefer_forward=args.prefer_forward,
        )
        run_record = snapshot["run_record"]

        output = {
            "run_id": run_record["run_id"],
            "mode": run_record["mode"],
            "target_date": run_record["target_date"],
            "forecast_peak_mw": run_record["forecast_peak_mw"],
            "peak_window_label": run_record["peak_window_label"],
            "overall_risk_level": run_record["overall_risk_level"],
            "operator_headline": run_record.get("operator_headline"),
            "logging_mode": get_forecast_run_logging_mode(),
        }

        if args.persist:
            run_ok, run_status = persist_forecast_run_record(run_record)
            briefing_ok, briefing_status = persist_briefing_snapshot(run_record)
            output["persist_run_ok"] = run_ok
            output["persist_run_status"] = run_status
            output["persist_briefing_ok"] = briefing_ok
            output["persist_briefing_status"] = briefing_status

        success_event = build_execution_event(
            job_name="daily_forecast_snapshot",
            status="success",
            started_at_utc=started_at,
            ended_at_utc=datetime.now(timezone.utc),
            run_record=run_record,
            message="Daily forecast snapshot job completed successfully.",
        )
        if args.persist:
            event_ok, event_status = persist_execution_event(success_event)
            output["persist_execution_ok"] = event_ok
            output["persist_execution_status"] = event_status

        print(json.dumps(output, indent=2, default=str))
    except Exception as exc:
        failure_event = build_execution_event(
            job_name="daily_forecast_snapshot",
            status="failure",
            started_at_utc=started_at,
            ended_at_utc=datetime.now(timezone.utc),
            run_record=None,
            message="Daily forecast snapshot job failed.",
            error_message=str(exc),
        )
        output = {
            "status": "failure",
            "logging_mode": get_forecast_run_logging_mode(),
            "error": str(exc),
        }
        if args.persist:
            event_ok, event_status = persist_execution_event(failure_event)
            output["persist_execution_ok"] = event_ok
            output["persist_execution_status"] = event_status

        print(json.dumps(output, indent=2, default=str))
        raise


if __name__ == "__main__":
    main()
