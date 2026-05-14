# Daily Snapshot Automation

This document explains how to automate daily forecast snapshot generation and saved briefing history.

## Why automation is needed

The dashboard can generate forecasts interactively, but a production workflow should not depend only on manual page visits.

A scheduled job helps the system:

- create a forecast snapshot at a fixed time each day
- generate the operator briefing automatically
- preserve a historical trail of daily briefing snapshots
- support shift handover and audit review

## What was implemented

The project now includes:

- reusable snapshot logic in `utils/forecast_snapshot.py`
- a runnable job script in `scripts/run_daily_forecast_snapshot.py`
- briefing snapshot persistence support
- dashboard history views in `Production Readiness`

## Recommended command

Run this from the repository root:

```powershell
python scripts/run_daily_forecast_snapshot.py --weather-signal "Apparent Temperature" --lookback-days 7 --prefer-forward --persist
```

## What the command does

1. Loads SCADA and weather data
2. Tries to generate a forward-looking forecast using Open-Meteo when requested
3. Falls back to historical backtest if forward weather is unavailable
4. Builds the operator briefing
5. Saves:
- forecast run record
- daily briefing snapshot

This persistence happens only when:

- `MONGODB_URI` is configured
- `ENABLE_FORECAST_RUN_LOGGING = "true"`

## Output collections

When persistence is enabled, the job writes to:

- `SCADA_AGENT.Forecast_run_logs`
- `SCADA_AGENT.Forecast_briefing_history`

## Suggested schedule

Run once per day before the operations shift starts.

Examples:

- `05:30` local time for morning shift preparation
- `23:30` local time for next-day readiness review

## Where to schedule it

This project is best scheduled outside Streamlit, using one of:

- Windows Task Scheduler
- cron
- Airflow
- a CI/CD runner
- any internal job orchestrator

## Windows Task Scheduler example

### Program/script

```text
python
```

### Arguments

```text
scripts/run_daily_forecast_snapshot.py --weather-signal "Apparent Temperature" --lookback-days 7 --prefer-forward --persist
```

### Start in

```text
D:\Self_Learning\scada-agent-project -Anti_Gravity - Copy\scada-streamlit-public
```

## How to verify it worked

Inside the app:

1. Open `Production Readiness`
2. Check `Forecast Registry`
3. Check `Operator Briefing`

You should see:

- new recent forecast run entries
- new saved briefing history

## Recommended next production step

After scheduling is in place, the strongest next step is:

1. attach execution status monitoring
2. capture job success/failure reason
3. extend observability to scheduled forecast runs

That completes the move from interactive forecasting to operational automation.
