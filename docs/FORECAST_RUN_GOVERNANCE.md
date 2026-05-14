# Forecast Run Governance

This document explains the forecast run registry added to support production-grade traceability.

## Why forecast governance matters

In a production system, a forecast should not exist only as a number on a chart.

We should also know:

- when it was generated
- which model version produced it
- whether it was a backtest or forward outlook
- which weather signal was used
- which data window and filters were active
- whether the run was persisted or kept only in the current session
- whether any fallback happened

This information is what makes a forecast explainable and auditable.

## What is now implemented

The app now creates a structured forecast run record whenever the Forecasting page generates a forecast.

### Logged fields

Each run record captures:

- `run_id`
- `created_at_utc`
- `model_version`
- `mode`
- `target_date`
- `lookback_days`
- `weather_signal`
- `weather_column`
- `forecast_peak_mw`
- `forecast_peak_time`
- `peak_window_label`
- `forecast_avg_mw`
- `forecast_energy_gwh`
- `actual_peak_mw` when available
- `actual_peak_time` when available
- `actual_energy_gwh` when available
- `mae_mw` when available
- `mape_pct` when available
- `overall_risk_level`
- `risk_flags`
- `risk_cards`
- `seasonality_warning`
- `data_source`
- active dashboard filters
- `logging_mode`
- `fallback_reason`

## Safe persistence design

The app is designed to stay safe by default.

### Default behavior

- forecast run records are captured in the current Streamlit session
- they are visible in `Production Readiness > Forecast Registry`
- no database write happens unless explicitly enabled

### Optional persistence

If you want persisted run logging in MongoDB, set:

```toml
ENABLE_FORECAST_RUN_LOGGING = "true"
```

When this is enabled and MongoDB is configured, run records are written to:

- database: `SCADA_AGENT`
- collection: `Forecast_run_logs`

### Why opt-in is better

This app started as a public dashboard. Writing back to a database has operational consequences, so persistence is intentionally opt-in.

That makes the system safer while still allowing a production upgrade path.

## What the dashboard shows

### Forecasting page

After a forecast is generated, the page now shows:

- whether the run was persisted or only captured in session
- the run ID
- the model version
- a short explanation of what metadata is being logged

### Production Readiness > Forecast Registry

This tab shows:

- recent session forecast runs
- recent persisted forecast runs when enabled
- a short explanation of why the registry exists

## How to think about this as a learner

Forecast accuracy tells you whether the model is good.

Forecast governance tells you whether the system is trustworthy.

Both are needed for production use.

## Recommended next step after this

The strongest next step is:

1. add daily operator briefing generation
2. store summary text alongside forecast run records
3. then connect forecast execution metadata into broader observability

That will move the system from monitored prediction into operational communication.
