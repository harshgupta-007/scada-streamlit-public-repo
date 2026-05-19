from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.forecasting import build_intraday_forecast, weather_label


ROADMAP_PHASES = [
    {
        "phase": "Phase 1",
        "name": "Data Health and Forecast Monitoring",
        "goal": "Make the system trustworthy by validating inputs and measuring forecast quality every day.",
        "outcome": "Operators can immediately see whether data is complete, whether forecast quality is drifting, and where attention is needed.",
    },
    {
        "phase": "Phase 2",
        "name": "Model Governance and Observability",
        "goal": "Version forecast logic, compare model choices, detect drift, and observe failures or fallbacks clearly.",
        "outcome": "Every forecast can be explained by its inputs, settings, comparative quality, and recent stability trend.",
    },
    {
        "phase": "Phase 3",
        "name": "Automation and Daily Briefings",
        "goal": "Generate forecast runs on a schedule and publish short operator-ready summaries.",
        "outcome": "The system shifts from reactive dashboard usage to proactive operational support.",
    },
    {
        "phase": "Phase 4",
        "name": "Service Layer and Production Hardening",
        "goal": "Separate UI, data prep, and forecast execution into cleaner production components.",
        "outcome": "The app becomes easier to scale, test, and secure for long-term use.",
    },
]


FORECAST_VARIANTS = [
    {
        "variant_id": "demand_only",
        "variant_name": "Demand Only Baseline",
        "weather_col": None,
        "description": "Uses same-block demand history only, with no weather adjustment.",
    },
    {
        "variant_id": "apparent_temperature",
        "variant_name": "Weather-Aware Apparent Temperature",
        "weather_col": "apparent_temperature",
        "description": "Uses apparent temperature to adjust the same-block historical baseline.",
    },
    {
        "variant_id": "temperature_2m",
        "variant_name": "Weather-Aware Temperature",
        "weather_col": "temperature_2m",
        "description": "Uses air temperature to adjust the same-block historical baseline.",
    },
]


@dataclass
class MonitoringArtifacts:
    data_health: dict
    backtest_table: pd.DataFrame
    backtest_summary: dict


@dataclass
class VersionComparisonArtifacts:
    comparison_table: pd.DataFrame
    variant_summary: pd.DataFrame
    drift_summary: pd.DataFrame
    narrative: str


def _risk_level(score: float, moderate_cutoff: float, high_cutoff: float) -> str:
    if score >= high_cutoff:
        return "High"
    if score >= moderate_cutoff:
        return "Moderate"
    return "Low"


def build_data_health_report(scada_df: pd.DataFrame, merged_df: pd.DataFrame) -> dict:
    if scada_df.empty:
        return {
            "overall_status": "High",
            "summary": "SCADA data is not available, so the production monitoring layer cannot assess system health.",
            "cards": [],
            "daily_completeness": pd.DataFrame(),
            "null_table": pd.DataFrame(),
        }

    working_df = scada_df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])
    daily_blocks = (
        working_df.groupby(working_df["date"].dt.date)["block_no"]
        .nunique()
        .reset_index(name="blocks_present")
        .rename(columns={"date": "date"})
    )
    daily_blocks["expected_blocks"] = 96
    daily_blocks["completeness_pct"] = (daily_blocks["blocks_present"] / 96) * 100
    daily_blocks["missing_blocks"] = 96 - daily_blocks["blocks_present"]

    duplicate_pairs = int(working_df.duplicated(subset=["date", "block_no"]).sum())
    incomplete_days = int((daily_blocks["blocks_present"] < 96).sum())
    block_coverage = float(daily_blocks["completeness_pct"].mean())

    key_columns = [
        "demand_energy",
        "thermal_gen",
        "hydel_gen",
        "renewable_gen",
        "Raw_Freq",
    ]
    available_key_columns = [col for col in key_columns if col in working_df.columns]
    null_table = pd.DataFrame(
        [
            {
                "Column": col,
                "Missing (%)": round(float(working_df[col].isna().mean() * 100), 2),
            }
            for col in available_key_columns
        ]
    ).sort_values("Missing (%)", ascending=False)

    weather_cols = [
        "temperature_2m",
        "relativehumidity_2m",
        "windspeed_10m",
        "apparent_temperature",
        "precipitation",
    ]
    if merged_df.empty:
        weather_coverage_pct = 0.0
    else:
        available_weather_cols = [col for col in weather_cols if col in merged_df.columns]
        if available_weather_cols:
            weather_coverage_pct = float(
                merged_df[available_weather_cols].notna().all(axis=1).mean() * 100
            )
        else:
            weather_coverage_pct = 0.0

    cards = [
        {
            "title": "Block Completeness",
            "value": f"{block_coverage:.1f}%",
            "status": _risk_level(100 - block_coverage, 0.5, 2.0),
            "detail": (
                "Each day should ideally contain all 96 quarter-hour demand blocks."
            ),
        },
        {
            "title": "Duplicate Date-Block Rows",
            "value": f"{duplicate_pairs}",
            "status": "High" if duplicate_pairs > 0 else "Low",
            "detail": "Duplicate rows make trend, anomaly, and forecast calculations unreliable.",
        },
        {
            "title": "Incomplete Days",
            "value": f"{incomplete_days}",
            "status": "High" if incomplete_days > 0 else "Low",
            "detail": "A day with missing blocks can distort intraday, weather, and forecast outputs.",
        },
        {
            "title": "Weather Merge Coverage",
            "value": f"{weather_coverage_pct:.1f}%",
            "status": _risk_level(100 - weather_coverage_pct, 1.0, 5.0),
            "detail": "This shows how much of the selected SCADA data is matched with usable weather records.",
        },
    ]

    overall_rank = max({"Low": 1, "Moderate": 2, "High": 3}[card["status"]] for card in cards)
    overall_status = {1: "Low", 2: "Moderate", 3: "High"}[overall_rank]
    summary = (
        "Data quality looks stable for the current selection."
        if overall_status == "Low"
        else "Some quality issues are visible and should be monitored before trusting all downstream analytics."
        if overall_status == "Moderate"
        else "Data quality has material issues that can directly affect dashboard outputs and forecast reliability."
    )

    return {
        "overall_status": overall_status,
        "summary": summary,
        "cards": cards,
        "daily_completeness": daily_blocks.sort_values("date"),
        "null_table": null_table,
    }


@st.cache_data(ttl=900, show_spinner=False)
def build_backtest_monitoring(
    df: pd.DataFrame,
    weather_col: str = "apparent_temperature",
    lookback_days: int = 7,
    evaluation_days: int = 7,
) -> tuple[pd.DataFrame, dict]:
    if df.empty:
        return pd.DataFrame(), {}

    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])
    unique_dates = sorted(working_df["date"].dt.date.unique())
    eligible_dates = unique_dates[max(lookback_days, 5):]
    target_dates = eligible_dates[-evaluation_days:]

    rows = []
    for target_date in target_dates:
        artifacts = build_intraday_forecast(
            working_df,
            target_date=target_date,
            weather_col=weather_col,
            lookback_days=lookback_days,
        )
        if artifacts is None:
            continue

        summary = artifacts.summary
        forecast_peak_time = summary["forecast_peak_time"]
        actual_peak_time = summary["actual_peak_time"]
        peak_time_hit = forecast_peak_time == actual_peak_time
        forecast_peak_block = artifacts.profile.loc[artifacts.profile["forecast_demand"].idxmax(), "block_no"]
        actual_peak_block = artifacts.profile.loc[artifacts.profile["demand_energy"].idxmax(), "block_no"]
        peak_block_error = abs(int(forecast_peak_block) - int(actual_peak_block))

        rows.append(
            {
                "Date": pd.to_datetime(target_date),
                "Forecast Peak (MW)": round(summary["forecast_peak_mw"], 0),
                "Actual Peak (MW)": round(summary["actual_peak_mw"], 0),
                "Peak Error (MW)": round(abs(summary["forecast_peak_mw"] - summary["actual_peak_mw"]), 0),
                "Forecast Energy (GWh)": round(summary["forecast_energy_gwh"], 2),
                "Actual Energy (GWh)": round(summary["actual_energy_gwh"], 2),
                "Energy Error (GWh)": round(abs(summary["forecast_energy_gwh"] - summary["actual_energy_gwh"]), 2),
                "MAE (MW)": round(summary["mae_mw"], 0),
                "MAPE (%)": round(summary["mape"] * 100, 2) if summary["mape"] == summary["mape"] else None,
                "Forecast Peak Time": forecast_peak_time,
                "Actual Peak Time": actual_peak_time,
                "Peak Block Error": peak_block_error,
                "Peak Time Hit": peak_time_hit,
                "Overall Risk": summary["overall_risk_level"],
            }
        )

    results_df = pd.DataFrame(rows)
    if results_df.empty:
        return results_df, {}

    summary = {
        "runs": int(len(results_df)),
        "avg_mape": float(results_df["MAPE (%)"].dropna().mean()),
        "avg_mae": float(results_df["MAE (MW)"].mean()),
        "avg_peak_error": float(results_df["Peak Error (MW)"].mean()),
        "avg_energy_error": float(results_df["Energy Error (GWh)"].mean()),
        "peak_time_hit_rate": float(results_df["Peak Time Hit"].mean() * 100),
        "status": _risk_level(float(results_df["MAPE (%)"].dropna().mean()), 3.0, 6.0),
    }
    return results_df, summary


@st.cache_data(ttl=900, show_spinner=False)
def build_forecast_version_comparison(
    df: pd.DataFrame,
    lookback_days: int = 7,
    evaluation_days: int = 7,
    variants: list[dict] | None = None,
) -> VersionComparisonArtifacts:
    if df.empty:
        return VersionComparisonArtifacts(
            comparison_table=pd.DataFrame(),
            variant_summary=pd.DataFrame(),
            drift_summary=pd.DataFrame(),
            narrative="No data is available for version comparison.",
        )

    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"])
    unique_dates = sorted(working_df["date"].dt.date.unique())
    eligible_dates = unique_dates[max(lookback_days, 5):]
    target_dates = eligible_dates[-evaluation_days:]
    active_variants = variants or FORECAST_VARIANTS

    rows = []
    for variant in active_variants:
        for target_date in target_dates:
            artifacts = build_intraday_forecast(
                working_df,
                target_date=target_date,
                weather_col=variant["weather_col"],
                lookback_days=lookback_days,
            )
            if artifacts is None:
                continue

            summary = artifacts.summary
            forecast_peak_block = artifacts.profile.loc[artifacts.profile["forecast_demand"].idxmax(), "block_no"]
            actual_peak_block = artifacts.profile.loc[artifacts.profile["demand_energy"].idxmax(), "block_no"]
            mape_pct = round(summary["mape"] * 100, 2) if summary["mape"] == summary["mape"] else None

            rows.append(
                {
                    "Date": pd.to_datetime(target_date),
                    "Variant ID": variant["variant_id"],
                    "Variant": variant["variant_name"],
                    "Weather Signal": (
                        weather_label(variant["weather_col"]) if variant["weather_col"] else "Demand Only"
                    ),
                    "MAPE (%)": mape_pct,
                    "MAE (MW)": round(summary["mae_mw"], 0),
                    "Peak Error (MW)": round(abs(summary["forecast_peak_mw"] - summary["actual_peak_mw"]), 0),
                    "Energy Error (GWh)": round(abs(summary["forecast_energy_gwh"] - summary["actual_energy_gwh"]), 2),
                    "Peak Time Hit": summary["forecast_peak_time"] == summary["actual_peak_time"],
                    "Peak Block Error": abs(int(forecast_peak_block) - int(actual_peak_block)),
                    "Overall Risk": summary["overall_risk_level"],
                }
            )

    comparison_df = pd.DataFrame(rows)
    if comparison_df.empty:
        return VersionComparisonArtifacts(
            comparison_table=comparison_df,
            variant_summary=pd.DataFrame(),
            drift_summary=pd.DataFrame(),
            narrative="Not enough eligible forecast history is available for version comparison.",
        )

    variant_summary = (
        comparison_df.groupby(["Variant", "Weather Signal"], as_index=False)
        .agg(
            Runs=("Date", "count"),
            Avg_MAPE_pct=("MAPE (%)", "mean"),
            Avg_MAE_mw=("MAE (MW)", "mean"),
            Avg_Peak_Error_mw=("Peak Error (MW)", "mean"),
            Avg_Energy_Error_gwh=("Energy Error (GWh)", "mean"),
            Peak_Time_Hit_Rate_pct=("Peak Time Hit", lambda x: float(x.mean() * 100)),
        )
        .sort_values(["Avg_MAPE_pct", "Avg_MAE_mw"], ascending=[True, True])
    )

    drift_rows = []
    for variant_name, group in comparison_df.sort_values("Date").groupby("Variant"):
        ordered = group.dropna(subset=["MAPE (%)"]).sort_values("Date").reset_index(drop=True)
        if ordered.empty:
            continue
        midpoint = max(len(ordered) // 2, 1)
        early = ordered.iloc[:midpoint]
        recent = ordered.iloc[midpoint:]
        if recent.empty:
            recent = early

        early_mape = float(early["MAPE (%)"].mean())
        recent_mape = float(recent["MAPE (%)"].mean())
        mape_shift = recent_mape - early_mape
        if mape_shift >= 0.5:
            drift_status = "Worsening"
        elif mape_shift <= -0.5:
            drift_status = "Improving"
        else:
            drift_status = "Stable"

        drift_rows.append(
            {
                "Variant": variant_name,
                "Early Window MAPE (%)": round(early_mape, 2),
                "Recent Window MAPE (%)": round(recent_mape, 2),
                "MAPE Shift (pct pts)": round(mape_shift, 2),
                "Recent MAE (MW)": round(float(recent["MAE (MW)"].mean()), 2),
                "Recent Peak Error (MW)": round(float(recent["Peak Error (MW)"].mean()), 2),
                "Drift Status": drift_status,
            }
        )

    drift_df = pd.DataFrame(drift_rows).sort_values(
        by=["MAPE Shift (pct pts)", "Recent Window MAPE (%)"],
        ascending=[True, True],
    ) if drift_rows else pd.DataFrame()

    best_variant = variant_summary.iloc[0] if not variant_summary.empty else None
    drift_headline = ""
    if not drift_df.empty:
        worsening = drift_df[drift_df["Drift Status"] == "Worsening"]["Variant"].tolist()
        improving = drift_df[drift_df["Drift Status"] == "Improving"]["Variant"].tolist()
        if worsening:
            drift_headline = "Recent drift warning: " + ", ".join(worsening) + " is degrading."
        elif improving:
            drift_headline = "Recent drift view: " + ", ".join(improving) + " is improving."
        else:
            drift_headline = "Recent drift view: the tested forecast variants are broadly stable."

    if best_variant is not None:
        narrative = (
            f"Best recent variant is {best_variant['Variant']} with average MAPE of "
            f"{best_variant['Avg_MAPE_pct']:.2f}% across {int(best_variant['Runs'])} backtest days. "
            f"{drift_headline}"
        ).strip()
    else:
        narrative = drift_headline or "Version comparison is available, but no strong winner is visible yet."

    return VersionComparisonArtifacts(
        comparison_table=comparison_df,
        variant_summary=variant_summary,
        drift_summary=drift_df,
        narrative=narrative,
    )


def build_monitoring_artifacts(
    scada_df: pd.DataFrame,
    merged_df: pd.DataFrame,
    weather_col: str = "apparent_temperature",
    lookback_days: int = 7,
    evaluation_days: int = 7,
) -> MonitoringArtifacts:
    data_health = build_data_health_report(scada_df, merged_df)
    backtest_table, backtest_summary = build_backtest_monitoring(
        merged_df if not merged_df.empty else scada_df,
        weather_col=weather_col,
        lookback_days=lookback_days,
        evaluation_days=evaluation_days,
    )
    return MonitoringArtifacts(
        data_health=data_health,
        backtest_table=backtest_table,
        backtest_summary=backtest_summary,
    )


def plot_daily_completeness(daily_df: pd.DataFrame):
    if daily_df.empty:
        return None
    fig = px.bar(
        daily_df,
        x="date",
        y="completeness_pct",
        title="Daily 96-Block Completeness",
        labels={"date": "Date", "completeness_pct": "Completeness (%)"},
    )
    fig.add_hline(y=100, line_dash="dot", line_color="#264653")
    fig.update_layout(template="plotly_white", hovermode="x unified")
    return fig


def plot_backtest_mape(results_df: pd.DataFrame):
    if results_df.empty:
        return None
    fig = px.line(
        results_df,
        x="Date",
        y="MAPE (%)",
        markers=True,
        title="Forecast Monitoring: MAPE by Evaluation Day",
        labels={"Date": "Target Date", "MAPE (%)": "MAPE (%)"},
    )
    fig.add_hline(y=3, line_dash="dot", line_color="#F4A261")
    fig.add_hline(y=6, line_dash="dot", line_color="#D62828")
    fig.update_layout(template="plotly_white", hovermode="x unified")
    return fig


def plot_peak_prediction_quality(results_df: pd.DataFrame):
    if results_df.empty:
        return None
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=results_df["Date"],
            y=results_df["Forecast Peak (MW)"],
            mode="lines+markers",
            name="Forecast Peak",
            line=dict(color="#1D4ED8", width=3),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=results_df["Date"],
            y=results_df["Actual Peak (MW)"],
            mode="lines+markers",
            name="Actual Peak",
            line=dict(color="#E76F51", width=2, dash="dot"),
        )
    )
    fig.update_layout(
        title="Forecast Monitoring: Peak Prediction Quality",
        xaxis_title="Target Date",
        yaxis_title="Peak Demand (MW)",
        template="plotly_white",
        hovermode="x unified",
    )
    return fig


def plot_variant_mape_comparison(comparison_df: pd.DataFrame):
    if comparison_df.empty:
        return None
    fig = px.line(
        comparison_df.sort_values("Date"),
        x="Date",
        y="MAPE (%)",
        color="Variant",
        markers=True,
        title="Forecast Version Comparison: MAPE by Day",
        labels={"Date": "Target Date", "MAPE (%)": "MAPE (%)"},
    )
    fig.add_hline(y=3, line_dash="dot", line_color="#F4A261")
    fig.add_hline(y=6, line_dash="dot", line_color="#D62828")
    fig.update_layout(template="plotly_white", hovermode="x unified", legend_title_text="Variant")
    return fig


def plot_variant_summary_bar(summary_df: pd.DataFrame):
    if summary_df.empty:
        return None
    plot_df = summary_df.rename(
        columns={
            "Avg_MAPE_pct": "Average MAPE (%)",
            "Peak_Time_Hit_Rate_pct": "Peak Time Hit Rate (%)",
        }
    )
    fig = px.bar(
        plot_df,
        x="Variant",
        y="Average MAPE (%)",
        color="Variant",
        text_auto=".2f",
        title="Forecast Version Comparison: Average Error by Variant",
    )
    fig.update_layout(template="plotly_white", showlegend=False)
    return fig


def plot_variant_drift(drift_df: pd.DataFrame):
    if drift_df.empty:
        return None
    plot_df = drift_df.melt(
        id_vars=["Variant", "Drift Status"],
        value_vars=["Early Window MAPE (%)", "Recent Window MAPE (%)"],
        var_name="Window",
        value_name="MAPE (%)",
    )
    fig = px.bar(
        plot_df,
        x="Variant",
        y="MAPE (%)",
        color="Window",
        barmode="group",
        title="Forecast Drift Analysis: Early vs Recent Error",
    )
    fig.update_layout(template="plotly_white", hovermode="x unified")
    return fig
