from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


WEATHER_LABELS = {
    "temperature_2m": "Temperature (deg C)",
    "relativehumidity_2m": "Relative Humidity (%)",
    "windspeed_10m": "Wind Speed (m/s)",
    "apparent_temperature": "Apparent Temperature (deg C)",
    "precipitation": "Precipitation (mm)",
}


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


def summarize_forecast(summary: dict) -> str:
    if not summary:
        return "Forecast summary is unavailable."

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
