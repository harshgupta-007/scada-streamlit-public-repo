import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.forecast_registry import (
    get_forecast_run_logging_mode,
    persist_briefing_snapshot,
    persist_forecast_run_record,
)
from utils.forecast_snapshot import generate_daily_snapshot


def main():
    parser = argparse.ArgumentParser(description="Generate and optionally persist a daily forecast snapshot.")
    parser.add_argument("--weather-signal", default="Apparent Temperature")
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--prefer-forward", action="store_true")
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()

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

    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
