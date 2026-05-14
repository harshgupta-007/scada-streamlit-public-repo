from __future__ import annotations

from typing import Optional

import pandas as pd


def _tone_from_risk(level: str) -> str:
    return {
        "High": "Priority attention is recommended.",
        "Moderate": "Closer monitoring is recommended.",
        "Low": "Normal monitoring should be sufficient.",
    }.get(level, "Normal monitoring should be sufficient.")


def _mode_label(summary: dict) -> str:
    return "forward outlook" if summary.get("mode") == "forward" else "historical backtest"


def build_operator_briefing(summary: dict, weather_signal_label: str) -> dict:
    if not summary:
        return {
            "headline": "Forecast briefing unavailable",
            "briefing_text": "The system could not build an operator briefing because forecast summary data is missing.",
            "sections": [],
        }

    risk_level = summary.get("overall_risk_level", "Low")
    target_date = summary.get("target_date")
    peak_mw = summary.get("forecast_peak_mw", 0.0)
    peak_window = summary.get("peak_window_label", "Unavailable")
    energy_gwh = summary.get("forecast_energy_gwh", 0.0)
    avg_mw = summary.get("forecast_avg_mw", 0.0)
    risk_flags = summary.get("risk_flags", [])
    risk_cards = summary.get("risk_cards", [])
    mode_label = _mode_label(summary)

    reliability_note = None
    if summary.get("seasonality_warning"):
        reliability_note = (
            "Reliability is reduced because the live forecast month sits outside the historical month pattern in the current demand dataset."
        )
    elif summary.get("mape") == summary.get("mape"):
        reliability_note = (
            f"Recent comparable backtest quality is about {summary['mape'] * 100:.1f}% MAPE and {summary['mae_mw']:,.0f} MW MAE."
        )
    else:
        reliability_note = "This is a forward outlook without same-day actuals yet, so monitor real-time deviation once operations begin."

    weather_note = None
    if summary.get("weather_summary") and summary.get("weather_col"):
        weather_info = summary["weather_summary"]
        weather_note = (
            f"{weather_signal_label} is a material input in this {mode_label}, with target-day average "
            f"{weather_info['avg_target_weather']:.1f} versus recent-history average {weather_info['avg_history_weather']:.1f}."
        )

    key_risk_lines = [
        f"{card['title']}: {card['level']} ({card['metric']})"
        for card in risk_cards
    ]

    headline = (
        f"{target_date} {mode_label.title()}: {risk_level} operational risk"
    )
    briefing_text = " ".join(
        [
            f"For {target_date}, the system expects a peak demand of {peak_mw:,.0f} MW, most likely during {peak_window}.",
            f"Expected daily energy is {energy_gwh:.2f} GWh with average demand around {avg_mw:,.0f} MW.",
            _tone_from_risk(risk_level),
            reliability_note,
        ]
        + ([weather_note] if weather_note else [])
    )

    sections = [
        {
            "title": "Expected Operating Shape",
            "body": f"Peak demand is expected around {peak_window} at about {peak_mw:,.0f} MW, with daily energy near {energy_gwh:.2f} GWh.",
        },
        {
            "title": "Risk View",
            "body": " | ".join(key_risk_lines) if key_risk_lines else "No additional risk-card details are available.",
        },
        {
            "title": "Operational Watchpoints",
            "body": " ".join(risk_flags) if risk_flags else "No special watchpoints are currently flagged.",
        },
        {
            "title": "Reliability Note",
            "body": reliability_note,
        },
    ]
    if weather_note:
        sections.append(
            {
                "title": "Weather Context",
                "body": weather_note,
            }
        )

    return {
        "headline": headline,
        "briefing_text": briefing_text,
        "sections": sections,
    }


def build_briefing_dataframe(briefing: dict) -> pd.DataFrame:
    sections = briefing.get("sections", [])
    if not sections:
        return pd.DataFrame()
    return pd.DataFrame(
        [{"Section": section["title"], "Details": section["body"]} for section in sections]
    )
