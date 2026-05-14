from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from utils.data_loader import filter_data_by_date, get_merged_scada_weather, load_scada_data
from utils.forecasting import (
    build_intraday_forecast,
    build_live_forecast,
    fetch_open_meteo_forecast_weather,
    get_forecast_target_dates,
)
from utils.forecast_registry import build_forecast_run_record
from utils.operator_briefing import build_operator_briefing


WEATHER_OPTION_MAP = {
    "Apparent Temperature": "apparent_temperature",
    "Temperature": "temperature_2m",
    "Relative Humidity": "relativehumidity_2m",
    "Wind Speed": "windspeed_10m",
    "Precipitation": "precipitation",
    "Demand Only Baseline": "__demand_only__",
}


def _filter_frames(scada_df: pd.DataFrame, merged_df: pd.DataFrame, filters: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    if start_date and end_date:
        scada_df = filter_data_by_date(scada_df, start_date, end_date)
        if not merged_df.empty:
            merged_df = filter_data_by_date(merged_df, start_date, end_date)

    for flag_name, column_name in [
        ("exclude_weekends", "is_weekend"),
        ("exclude_holidays", "is_holiday"),
        ("exclude_events", "is_special_event"),
    ]:
        if filters.get(flag_name, False):
            if column_name in scada_df.columns:
                scada_df = scada_df[~scada_df[column_name]]
            if not merged_df.empty and column_name in merged_df.columns:
                merged_df = merged_df[~merged_df[column_name]]

    return scada_df, merged_df


def generate_daily_snapshot(
    weather_signal_label: str = "Apparent Temperature",
    lookback_days: int = 7,
    filters: Optional[dict] = None,
    prefer_forward: bool = True,
) -> dict:
    filters = filters or {}
    scada_df = load_scada_data()
    merged_df = get_merged_scada_weather()
    scada_df, merged_df = _filter_frames(scada_df, merged_df, filters)

    working_df = merged_df if not merged_df.empty else scada_df
    if working_df.empty:
        raise ValueError("No data is available to generate a daily forecast snapshot.")

    weather_col = WEATHER_OPTION_MAP.get(weather_signal_label, "apparent_temperature")
    fallback_reason = None
    artifacts = None

    if prefer_forward and weather_col != "__demand_only__":
        try:
            forecast_weather_df = fetch_open_meteo_forecast_weather(forecast_days=3)
        except Exception as exc:
            forecast_weather_df = pd.DataFrame()
            fallback_reason = str(exc)

        if not forecast_weather_df.empty:
            future_dates = sorted(forecast_weather_df["date"].dt.date.unique())
            target_date = future_dates[min(1, len(future_dates) - 1)] if future_dates else None
            if target_date:
                artifacts = build_live_forecast(
                    working_df,
                    forecast_weather_df=forecast_weather_df,
                    target_date=target_date,
                    weather_col=weather_col,
                    lookback_days=lookback_days,
                )

    if artifacts is None:
        eligible_dates = get_forecast_target_dates(working_df, min_history_days=5)
        if not eligible_dates:
            raise ValueError("Not enough eligible dates are available for a historical backtest snapshot.")
        target_date = eligible_dates[-1]
        artifacts = build_intraday_forecast(
            working_df,
            target_date=target_date,
            weather_col=weather_col if weather_col != "__demand_only__" else "__no_weather__",
            lookback_days=lookback_days,
        )
        if artifacts is None:
            raise ValueError("The historical backtest snapshot could not be generated.")

    summary = artifacts.summary
    briefing = build_operator_briefing(summary, weather_signal_label)
    run_record = build_forecast_run_record(
        summary,
        weather_signal_label=weather_signal_label,
        filters=filters,
        operator_briefing=briefing,
        fallback_reason=fallback_reason,
    )
    run_record["snapshot_generated_by"] = "daily_snapshot_job"
    run_record["snapshot_generated_local"] = datetime.now().isoformat(timespec="seconds")
    run_record["snapshot_prefer_forward"] = bool(prefer_forward)

    return {
        "artifacts": artifacts,
        "summary": summary,
        "briefing": briefing,
        "run_record": run_record,
    }
