from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Optional
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import pandas as pd
import streamlit as st


WEATHER_LABELS = {
    "temperature_2m": "Temperature (deg C)",
    "relativehumidity_2m": "Relative Humidity (%)",
    "windspeed_10m": "Wind Speed (m/s)",
    "apparent_temperature": "Apparent Temperature (deg C)",
    "precipitation": "Precipitation (mm)",
}

DEFAULT_OPEN_METEO_LATITUDE = 21.8129
DEFAULT_OPEN_METEO_LONGITUDE = 80.1838
DEFAULT_OPEN_METEO_TIMEZONE = "Asia/Kolkata"


def block_to_time(block_no: int) -> str:
    minutes = (int(block_no) - 1) * 15
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def weather_label(weather_col: str) -> str:
    return WEATHER_LABELS.get(weather_col, weather_col.replace("_", " ").title())


def get_forecast_target_dates(df: pd.DataFrame, min_history_days: int = 5) -> list:
    if df.empty or "date" not in df.columns:
        return []

    ordered_dates = sorted(pd.to_datetime(df["date"]).dt.date.unique())
    return ordered_dates[min_history_days:]


def _calc_weather_beta(group: pd.DataFrame, weather_col: str) -> float:
    valid_group = group[["demand_energy", weather_col]].dropna()
    if len(valid_group) < 3:
        return 0.0

    weather_values = valid_group[weather_col].astype(float).to_numpy()
    demand_values = valid_group["demand_energy"].astype(float).to_numpy()
    weather_var = np.var(weather_values)
    if weather_var <= 0:
        return 0.0

    covariance = np.cov(weather_values, demand_values, ddof=0)[0, 1]
    return float(covariance / weather_var)


@dataclass
class ForecastArtifacts:
    profile: pd.DataFrame
    recent_daily: pd.DataFrame
    summary: dict


def _risk_level_from_score(score: float, medium_cutoff: float = 0.5, high_cutoff: float = 1.25) -> str:
    if score >= high_cutoff:
        return "High"
    if score >= medium_cutoff:
        return "Moderate"
    return "Low"


def _build_peak_window(profile: pd.DataFrame) -> tuple[str, str, str]:
    peak_idx = profile["forecast_demand"].idxmax()
    peak_row = profile.loc[peak_idx]
    peak_threshold = float(peak_row["forecast_demand"]) * 0.985
    near_peak = profile[profile["forecast_demand"] >= peak_threshold].sort_values("block_no")
    if near_peak.empty:
        start_block = end_block = int(peak_row["block_no"])
    else:
        block_list = near_peak["block_no"].astype(int).tolist()
        peak_block = int(peak_row["block_no"])
        segments = [[block_list[0]]]
        for block in block_list[1:]:
            if block == segments[-1][-1] + 1:
                segments[-1].append(block)
            else:
                segments.append([block])
        chosen_segment = next((segment for segment in segments if peak_block in segment), [peak_block])
        start_block = min(chosen_segment)
        end_block = max(chosen_segment)

    start_time = block_to_time(start_block)
    end_time = block_to_time(min(end_block + 1, 96))
    return start_time, end_time, f"{start_time} to {end_time}"


def get_open_meteo_settings() -> dict:
    try:
        latitude = float(st.secrets.get("OPEN_METEO_LATITUDE", DEFAULT_OPEN_METEO_LATITUDE))
    except Exception:
        latitude = DEFAULT_OPEN_METEO_LATITUDE
    try:
        longitude = float(st.secrets.get("OPEN_METEO_LONGITUDE", DEFAULT_OPEN_METEO_LONGITUDE))
    except Exception:
        longitude = DEFAULT_OPEN_METEO_LONGITUDE
    try:
        timezone = str(st.secrets.get("OPEN_METEO_TIMEZONE", DEFAULT_OPEN_METEO_TIMEZONE))
    except Exception:
        timezone = DEFAULT_OPEN_METEO_TIMEZONE

    return {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone,
    }


@st.cache_data(ttl=3600)
def fetch_open_meteo_forecast_weather(forecast_days: int = 3) -> pd.DataFrame:
    settings = get_open_meteo_settings()
    params = {
        "latitude": settings["latitude"],
        "longitude": settings["longitude"],
        "timezone": settings["timezone"],
        "minutely_15": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "wind_speed_10m",
                "apparent_temperature",
                "precipitation",
            ]
        ),
        "forecast_minutely_15": max(96, min(96 * forecast_days, 96 * 7)),
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urlencode(params)

    with urlopen(url, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))

    minutely = payload.get("minutely_15", {})
    if not minutely or "time" not in minutely:
        return pd.DataFrame()

    forecast_df = pd.DataFrame(minutely)
    forecast_df["time"] = pd.to_datetime(forecast_df["time"])
    forecast_df = forecast_df.rename(
        columns={
            "relative_humidity_2m": "relativehumidity_2m",
            "wind_speed_10m": "windspeed_10m",
        }
    )
    forecast_df["date"] = forecast_df["time"].dt.normalize()
    forecast_df["block_no"] = (forecast_df["time"].dt.hour * 4) + (forecast_df["time"].dt.minute // 15) + 1
    forecast_df["hour"] = forecast_df["time"].dt.hour
    forecast_df["minute"] = forecast_df["time"].dt.minute
    forecast_df["day_of_week"] = forecast_df["time"].dt.day_name()
    forecast_df["month"] = forecast_df["time"].dt.month
    forecast_df["is_weekend"] = forecast_df["time"].dt.dayofweek >= 5
    forecast_df["latitude"] = settings["latitude"]
    forecast_df["longitude"] = settings["longitude"]

    return forecast_df[
        [
            "time",
            "date",
            "block_no",
            "hour",
            "minute",
            "day_of_week",
            "month",
            "is_weekend",
            "temperature_2m",
            "relativehumidity_2m",
            "windspeed_10m",
            "apparent_temperature",
            "precipitation",
            "latitude",
            "longitude",
        ]
    ]


def build_intraday_forecast(
    df: pd.DataFrame,
    target_date,
    weather_col: str = "apparent_temperature",
    lookback_days: int = 7,
) -> Optional[ForecastArtifacts]:
    required_columns = {"date", "block_no", "demand_energy"}
    if df.empty or not required_columns.issubset(df.columns):
        return None

    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])
    target_ts = pd.Timestamp(target_date)

    target_df = working_df[working_df["date"].dt.date == target_ts.date()].copy()
    if target_df.empty:
        return None

    available_history_dates = sorted(working_df.loc[working_df["date"] < target_ts, "date"].dt.normalize().unique())
    if len(available_history_dates) < max(3, lookback_days):
        return None

    history_dates = available_history_dates[-lookback_days:]
    history_df = working_df[working_df["date"].isin(history_dates)].copy()
    if history_df.empty:
        return None

    use_weather = weather_col in working_df.columns
    stats_map = {
        "demand_mean": ("demand_energy", "mean"),
        "demand_std": ("demand_energy", "std"),
    }
    if use_weather:
        stats_map["weather_mean"] = (weather_col, "mean")

    block_stats = history_df.groupby("block_no").agg(**stats_map).reset_index()
    block_stats["demand_std"] = block_stats["demand_std"].fillna(0.0)

    if use_weather:
        weather_betas = (
            history_df.groupby("block_no")[["demand_energy", weather_col]]
            .apply(lambda group: _calc_weather_beta(group, weather_col))
            .rename("weather_beta")
            .reset_index()
        )
        block_stats = block_stats.merge(weather_betas, on="block_no", how="left")
        block_stats["weather_beta"] = block_stats["weather_beta"].fillna(0.0)
    else:
        block_stats["weather_mean"] = np.nan
        block_stats["weather_beta"] = 0.0

    merged = target_df.merge(block_stats, on="block_no", how="left")
    merged = merged.dropna(subset=["demand_mean"])
    if merged.empty:
        return None

    if use_weather:
        merged["weather_adjustment"] = merged["weather_beta"] * (merged[weather_col] - merged["weather_mean"])
    else:
        merged["weather_adjustment"] = 0.0

    merged["forecast_demand"] = (merged["demand_mean"] + merged["weather_adjustment"]).clip(lower=0)
    merged["residual"] = merged["demand_energy"] - merged["forecast_demand"]

    residual_lookup = []
    for block_no, group in history_df.groupby("block_no"):
        demand_mean = float(group["demand_energy"].mean())
        demand_std = float(group["demand_energy"].std(ddof=0)) if len(group) > 1 else 0.0
        if use_weather:
            weather_mean = float(group[weather_col].mean())
            beta = float(block_stats.loc[block_stats["block_no"] == block_no, "weather_beta"].iloc[0])
            fitted = demand_mean + beta * (group[weather_col] - weather_mean)
            residual_std = float((group["demand_energy"] - fitted).std(ddof=0)) if len(group) > 1 else 0.0
        else:
            residual_std = demand_std
        residual_lookup.append(
            {
                "block_no": block_no,
                "residual_std": max(residual_std, demand_std * 0.35, 50.0),
            }
        )

    residual_df = pd.DataFrame(residual_lookup)
    merged = merged.merge(residual_df, on="block_no", how="left")
    merged["residual_std"] = merged["residual_std"].fillna(100.0)
    merged["forecast_lower"] = (merged["forecast_demand"] - 1.28 * merged["residual_std"]).clip(lower=0)
    merged["forecast_upper"] = merged["forecast_demand"] + 1.28 * merged["residual_std"]
    merged["time"] = merged["block_no"].apply(block_to_time)

    profile = merged[
        [
            "date",
            "block_no",
            "time",
            "demand_energy",
            "forecast_demand",
            "forecast_lower",
            "forecast_upper",
            "demand_mean",
            "weather_adjustment",
        ]
        + ([weather_col, "weather_mean", "weather_beta"] if use_weather else [])
    ].sort_values("block_no")

    daily_history = (
        history_df.groupby("date")["demand_energy"]
        .agg(avg_demand="mean", peak_demand="max", min_demand="min", total_energy_mwh="sum")
        .reset_index()
    )
    daily_history["total_energy_gwh"] = daily_history["total_energy_mwh"] * 0.25 / 1000

    forecast_peak_row = profile.loc[profile["forecast_demand"].idxmax()]
    actual_peak_row = profile.loc[profile["demand_energy"].idxmax()]
    peak_window_start, peak_window_end, peak_window_label = _build_peak_window(profile)

    actual_daily_energy_gwh = profile["demand_energy"].sum() * 0.25 / 1000
    forecast_daily_energy_gwh = profile["forecast_demand"].sum() * 0.25 / 1000
    mape = (
        (profile["demand_energy"] - profile["forecast_demand"]).abs() / profile["demand_energy"].replace(0, np.nan)
    ).dropna().mean()
    mae = (profile["demand_energy"] - profile["forecast_demand"]).abs().mean()

    recent_daily = daily_history.copy()
    recent_daily["date"] = pd.to_datetime(recent_daily["date"])

    profile["forecast_ramp"] = profile["forecast_demand"].diff().abs().fillna(0.0)
    recent_ramp = history_df.sort_values(["date", "block_no"]).groupby("date")["demand_energy"].diff().abs()
    recent_ramp = recent_ramp.groupby(history_df.sort_values(["date", "block_no"])["date"]).max().dropna()
    forecast_max_ramp = float(profile["forecast_ramp"].max())

    peak_mean = float(recent_daily["peak_demand"].mean())
    peak_std = float(recent_daily["peak_demand"].std(ddof=0))
    peak_threshold = peak_mean + peak_std
    ramp_mean = float(recent_ramp.mean()) if not recent_ramp.empty else 0.0
    ramp_std = float(recent_ramp.std(ddof=0)) if len(recent_ramp) > 1 else 0.0
    ramp_threshold = ramp_mean + ramp_std if not recent_ramp.empty else forecast_max_ramp + 1
    demand_bias = float(profile["weather_adjustment"].abs().mean()) if "weather_adjustment" in profile.columns else 0.0
    weather_bias_pct = demand_bias / max(float(profile["forecast_demand"].mean()), 1.0)

    peak_score = (float(forecast_peak_row["forecast_demand"]) - peak_mean) / peak_std if peak_std > 0 else 0.0
    ramp_score = (forecast_max_ramp - ramp_mean) / ramp_std if ramp_std > 0 else 0.0
    weather_score = max(
        demand_bias / 125.0,
        weather_bias_pct / 0.02,
    ) if use_weather else 0.0

    peak_level = _risk_level_from_score(peak_score)
    ramp_level = _risk_level_from_score(ramp_score)
    weather_level = _risk_level_from_score(weather_score, medium_cutoff=1.0, high_cutoff=2.0) if use_weather else "Low"

    risk_cards = [
        {
            "title": "Peak Risk",
            "level": peak_level,
            "metric": f"{forecast_peak_row['forecast_demand']:,.0f} MW",
            "detail": (
                "Forecast peak is materially above the recent operating band."
                if peak_level == "High"
                else "Forecast peak is somewhat elevated versus recent days."
                if peak_level == "Moderate"
                else "Forecast peak stays inside the recent operating band."
            ),
        },
        {
            "title": "Ramp Risk",
            "level": ramp_level,
            "metric": f"{forecast_max_ramp:,.0f} MW / 15 min",
            "detail": (
                "Intraday ramping looks sharp and may require closer balancing attention."
                if ramp_level == "High"
                else "Ramping is noticeable but still near the recent norm."
                if ramp_level == "Moderate"
                else "Ramping stays broadly normal."
            ),
        },
        {
            "title": "Weather Sensitivity",
            "level": weather_level,
            "metric": f"{demand_bias:,.0f} MW adj."
            if use_weather
            else "Demand only",
            "detail": (
                "Weather is strongly shifting the forecast curve."
                if weather_level == "High"
                else "Weather is influencing the forecast, but not dominating it."
                if weather_level == "Moderate"
                else "Weather effect is limited in this forecast setup."
            )
            if use_weather
            else "Demand-only baseline is active, so no weather adjustment is applied.",
        },
    ]

    overall_level = max(risk_cards, key=lambda item: {"Low": 1, "Moderate": 2, "High": 3}[item["level"]])["level"]

    risk_flags = []
    if float(forecast_peak_row["forecast_demand"]) >= float(peak_threshold):
        risk_flags.append("Predicted peak is above the recent average-plus-one-sigma band.")
    if forecast_max_ramp >= float(ramp_threshold):
        risk_flags.append("Predicted ramp intensity is unusually high for at least one 15-minute interval.")
    if use_weather and demand_bias >= 150:
        risk_flags.append("Weather adjustment is materially shaping the intraday demand curve.")
    if not risk_flags:
        risk_flags.append("Forecast sits within the recent operating band with no major stress flags.")

    weather_summary = None
    if use_weather and weather_col in target_df.columns:
        weather_summary = {
            "avg_target_weather": float(target_df[weather_col].mean()),
            "avg_history_weather": float(history_df[weather_col].mean()),
        }

    summary = {
        "mode": "backtest",
        "target_date": target_ts.date(),
        "lookback_days": len(history_dates),
        "weather_col": weather_col if use_weather else None,
        "forecast_peak_mw": float(forecast_peak_row["forecast_demand"]),
        "forecast_peak_time": str(forecast_peak_row["time"]),
        "peak_window_start": peak_window_start,
        "peak_window_end": peak_window_end,
        "peak_window_label": peak_window_label,
        "actual_peak_mw": float(actual_peak_row["demand_energy"]),
        "actual_peak_time": str(actual_peak_row["time"]),
        "forecast_avg_mw": float(profile["forecast_demand"].mean()),
        "actual_avg_mw": float(profile["demand_energy"].mean()),
        "forecast_energy_gwh": float(forecast_daily_energy_gwh),
        "actual_energy_gwh": float(actual_daily_energy_gwh),
        "mae_mw": float(mae),
        "mape": float(mape) if pd.notna(mape) else np.nan,
        "risk_flags": risk_flags,
        "risk_cards": risk_cards,
        "overall_risk_level": overall_level,
        "weather_summary": weather_summary,
    }

    return ForecastArtifacts(profile=profile, recent_daily=recent_daily, summary=summary)


def build_live_forecast(
    df: pd.DataFrame,
    forecast_weather_df: pd.DataFrame,
    target_date,
    weather_col: str = "apparent_temperature",
    lookback_days: int = 7,
) -> Optional[ForecastArtifacts]:
    required_columns = {"date", "block_no", "demand_energy"}
    if df.empty or forecast_weather_df.empty or not required_columns.issubset(df.columns):
        return None

    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])
    weather_df = forecast_weather_df.copy()
    weather_df["date"] = pd.to_datetime(weather_df["date"])
    target_ts = pd.Timestamp(target_date)

    target_df = weather_df[weather_df["date"].dt.date == target_ts.date()].copy()
    if target_df.empty or "block_no" not in target_df.columns or weather_col not in target_df.columns:
        return None

    numeric_weather_cols = [
        col
        for col in dict.fromkeys(
            [
                "temperature_2m",
                "relativehumidity_2m",
                "windspeed_10m",
                "apparent_temperature",
                "precipitation",
                weather_col,
            ]
        )
        if col in target_df.columns
    ]
    target_df = (
        target_df.groupby("block_no", as_index=False)[numeric_weather_cols]
        .mean()
        .assign(date=target_ts.normalize())
    )

    available_history_dates = sorted(working_df["date"].dt.normalize().unique())
    if len(available_history_dates) < max(3, lookback_days):
        return None

    history_dates = available_history_dates[-lookback_days:]
    history_df = working_df[working_df["date"].isin(history_dates)].copy()
    if history_df.empty:
        return None

    use_weather = weather_col in working_df.columns and weather_col in target_df.columns
    stats_map = {
        "demand_mean": ("demand_energy", "mean"),
        "demand_std": ("demand_energy", "std"),
    }
    if use_weather:
        stats_map["weather_mean"] = (weather_col, "mean")

    block_stats = history_df.groupby("block_no").agg(**stats_map).reset_index()
    block_stats["demand_std"] = block_stats["demand_std"].fillna(0.0)

    if use_weather:
        weather_betas = (
            history_df.groupby("block_no")[["demand_energy", weather_col]]
            .apply(lambda group: _calc_weather_beta(group, weather_col))
            .rename("weather_beta")
            .reset_index()
        )
        block_stats = block_stats.merge(weather_betas, on="block_no", how="left")
        block_stats["weather_beta"] = block_stats["weather_beta"].fillna(0.0)
    else:
        block_stats["weather_mean"] = np.nan
        block_stats["weather_beta"] = 0.0

    merged = target_df.merge(block_stats, on="block_no", how="left")
    merged = merged.dropna(subset=["demand_mean"])
    if merged.empty:
        return None

    if use_weather:
        merged["weather_adjustment"] = merged["weather_beta"] * (merged[weather_col] - merged["weather_mean"])
    else:
        merged["weather_adjustment"] = 0.0

    merged["forecast_demand"] = (merged["demand_mean"] + merged["weather_adjustment"]).clip(lower=0)
    merged["residual"] = np.nan

    residual_lookup = []
    for block_no, group in history_df.groupby("block_no"):
        demand_mean = float(group["demand_energy"].mean())
        demand_std = float(group["demand_energy"].std(ddof=0)) if len(group) > 1 else 0.0
        if use_weather:
            weather_mean = float(group[weather_col].mean())
            beta = float(block_stats.loc[block_stats["block_no"] == block_no, "weather_beta"].iloc[0])
            fitted = demand_mean + beta * (group[weather_col] - weather_mean)
            residual_std = float((group["demand_energy"] - fitted).std(ddof=0)) if len(group) > 1 else 0.0
        else:
            residual_std = demand_std
        residual_lookup.append(
            {
                "block_no": block_no,
                "residual_std": max(residual_std, demand_std * 0.35, 50.0),
            }
        )

    residual_df = pd.DataFrame(residual_lookup)
    merged = merged.merge(residual_df, on="block_no", how="left")
    merged["residual_std"] = merged["residual_std"].fillna(100.0)
    merged["forecast_lower"] = (merged["forecast_demand"] - 1.28 * merged["residual_std"]).clip(lower=0)
    merged["forecast_upper"] = merged["forecast_demand"] + 1.28 * merged["residual_std"]
    merged["time_label"] = merged["block_no"].apply(block_to_time)
    merged["demand_energy"] = np.nan

    profile = merged[
        [
            "date",
            "block_no",
            "time_label",
            "demand_energy",
            "forecast_demand",
            "forecast_lower",
            "forecast_upper",
            "demand_mean",
            "weather_adjustment",
        ]
        + ([weather_col, "weather_mean", "weather_beta"] if use_weather else [])
    ].sort_values("block_no").rename(columns={"time_label": "time"})

    daily_history = (
        history_df.groupby("date")["demand_energy"]
        .agg(avg_demand="mean", peak_demand="max", min_demand="min", total_energy_mwh="sum")
        .reset_index()
    )
    daily_history["total_energy_gwh"] = daily_history["total_energy_mwh"] * 0.25 / 1000
    recent_daily = daily_history.copy()
    recent_daily["date"] = pd.to_datetime(recent_daily["date"])

    forecast_peak_row = profile.loc[profile["forecast_demand"].idxmax()]
    peak_window_start, peak_window_end, peak_window_label = _build_peak_window(profile)
    forecast_daily_energy_gwh = profile["forecast_demand"].sum() * 0.25 / 1000

    profile["forecast_ramp"] = profile["forecast_demand"].diff().abs().fillna(0.0)
    recent_ramp = history_df.sort_values(["date", "block_no"]).groupby("date")["demand_energy"].diff().abs()
    recent_ramp = recent_ramp.groupby(history_df.sort_values(["date", "block_no"])["date"]).max().dropna()
    forecast_max_ramp = float(profile["forecast_ramp"].max())

    peak_mean = float(recent_daily["peak_demand"].mean())
    peak_std = float(recent_daily["peak_demand"].std(ddof=0))
    ramp_mean = float(recent_ramp.mean()) if not recent_ramp.empty else 0.0
    ramp_std = float(recent_ramp.std(ddof=0)) if len(recent_ramp) > 1 else 0.0
    demand_bias = float(profile["weather_adjustment"].abs().mean()) if "weather_adjustment" in profile.columns else 0.0
    weather_bias_pct = demand_bias / max(float(profile["forecast_demand"].mean()), 1.0)

    peak_score = (float(forecast_peak_row["forecast_demand"]) - peak_mean) / peak_std if peak_std > 0 else 0.0
    ramp_score = (forecast_max_ramp - ramp_mean) / ramp_std if ramp_std > 0 else 0.0
    weather_score = max(demand_bias / 125.0, weather_bias_pct / 0.02) if use_weather else 0.0

    peak_level = _risk_level_from_score(peak_score)
    ramp_level = _risk_level_from_score(ramp_score)
    weather_level = _risk_level_from_score(weather_score, medium_cutoff=1.0, high_cutoff=2.0) if use_weather else "Low"

    risk_cards = [
        {
            "title": "Peak Risk",
            "level": peak_level,
            "metric": f"{forecast_peak_row['forecast_demand']:,.0f} MW",
            "detail": (
                "Forecast peak is materially above the recent operating band."
                if peak_level == "High"
                else "Forecast peak is somewhat elevated versus recent days."
                if peak_level == "Moderate"
                else "Forecast peak stays inside the recent operating band."
            ),
        },
        {
            "title": "Ramp Risk",
            "level": ramp_level,
            "metric": f"{forecast_max_ramp:,.0f} MW / 15 min",
            "detail": (
                "Intraday ramping looks sharp and may require closer balancing attention."
                if ramp_level == "High"
                else "Ramping is noticeable but still near the recent norm."
                if ramp_level == "Moderate"
                else "Ramping stays broadly normal."
            ),
        },
        {
            "title": "Weather Sensitivity",
            "level": weather_level,
            "metric": f"{demand_bias:,.0f} MW adj." if use_weather else "Demand only",
            "detail": (
                "Weather is strongly shifting the forecast curve."
                if weather_level == "High"
                else "Weather is influencing the forecast, but not dominating it."
                if weather_level == "Moderate"
                else "Weather effect is limited in this forecast setup."
            )
            if use_weather
            else "Demand-only baseline is active, so no weather adjustment is applied.",
        },
    ]
    overall_level = max(risk_cards, key=lambda item: {"Low": 1, "Moderate": 2, "High": 3}[item["level"]])["level"]

    history_months = sorted({int(month) for month in working_df["date"].dt.month.unique()})
    seasonality_warning = target_ts.month not in history_months

    risk_flags = [
        f"Open-Meteo forward weather forecast is being used for {target_ts.date()} at 15-minute resolution.",
    ]
    if peak_level == "High":
        risk_flags.append("Predicted peak is above the recent operating band.")
    if ramp_level == "High":
        risk_flags.append("Predicted ramp intensity is unusually high.")
    if seasonality_warning:
        risk_flags.append(
            "Forecast month is outside the historical month pattern in the current demand dataset, so reliability is lower."
        )
    if not seasonality_warning and peak_level == "Low" and ramp_level == "Low" and weather_level == "Low":
        risk_flags.append("Forecast sits within the recent operating band with no major stress flags.")

    weather_summary = None
    if use_weather:
        weather_summary = {
            "avg_target_weather": float(target_df[weather_col].mean()),
            "avg_history_weather": float(history_df[weather_col].mean()),
        }

    summary = {
        "mode": "forward",
        "target_date": target_ts.date(),
        "lookback_days": len(history_dates),
        "weather_col": weather_col if use_weather else None,
        "forecast_peak_mw": float(forecast_peak_row["forecast_demand"]),
        "forecast_peak_time": str(forecast_peak_row["time"]),
        "peak_window_start": peak_window_start,
        "peak_window_end": peak_window_end,
        "peak_window_label": peak_window_label,
        "actual_peak_mw": np.nan,
        "actual_peak_time": None,
        "forecast_avg_mw": float(profile["forecast_demand"].mean()),
        "actual_avg_mw": np.nan,
        "forecast_energy_gwh": float(forecast_daily_energy_gwh),
        "actual_energy_gwh": np.nan,
        "mae_mw": np.nan,
        "mape": np.nan,
        "risk_flags": risk_flags,
        "risk_cards": risk_cards,
        "overall_risk_level": overall_level,
        "weather_summary": weather_summary,
        "seasonality_warning": seasonality_warning,
    }

    return ForecastArtifacts(profile=profile, recent_daily=recent_daily, summary=summary)


def summarize_forecast(summary: dict) -> str:
    if not summary:
        return "Forecast summary is unavailable."

    if summary.get("mode") == "forward":
        lines = [
            (
                f"Forward forecast for {summary['target_date']}: predicted peak demand is "
                f"{summary['forecast_peak_mw']:,.0f} MW, most likely within {summary['peak_window_label']}, "
                f"with predicted daily energy of {summary['forecast_energy_gwh']:.2f} GWh."
            ),
        ]
        if summary.get("weather_summary"):
            weather_info = summary["weather_summary"]
            lines.append(
                "Live Open-Meteo weather forecast used "
                f"{weather_label(summary['weather_col']).lower()} with target-day average "
                f"{weather_info['avg_target_weather']:.1f} versus history average "
                f"{weather_info['avg_history_weather']:.1f}."
            )
        if summary.get("seasonality_warning"):
            lines.append(
                "Reliability note: the live forecast month is outside the historical demand month pattern available in this dataset."
            )
        lines.append("Risk outlook: " + " ".join(summary["risk_flags"]))
        return " ".join(lines)

    lines = [
        (
            f"Forecast for {summary['target_date']}: predicted peak demand is "
            f"{summary['forecast_peak_mw']:,.0f} MW at {summary['forecast_peak_time']}, with "
            f"predicted daily energy of {summary['forecast_energy_gwh']:.2f} GWh."
        ),
        (
            f"Against the actual day, the model is off by {summary['mae_mw']:,.0f} MW on average "
            f"and {summary['mape'] * 100:.1f}% MAPE."
            if pd.notna(summary["mape"])
            else f"Against the actual day, the model is off by {summary['mae_mw']:,.0f} MW on average."
        ),
    ]

    if summary.get("weather_summary"):
        weather_info = summary["weather_summary"]
        lines.append(
            "Weather-aware adjustment used "
            f"{weather_label(summary['weather_col']).lower()} with target-day average "
            f"{weather_info['avg_target_weather']:.1f} versus history average "
            f"{weather_info['avg_history_weather']:.1f}."
        )

    lines.append("Risk outlook: " + " ".join(summary["risk_flags"]))
    return " ".join(lines)
