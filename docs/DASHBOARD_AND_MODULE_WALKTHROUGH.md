# Dashboard and Module Walkthrough

This guide is meant to help a new reviewer, operator, developer, or learner understand the project clearly without reading every file first.

If someone reads this document from top to bottom, they should understand:

- what the dashboard does
- how each page is used
- how the data moves through the system
- what each main module is responsible for
- how the production-grade layers fit together

This document should be updated whenever a major feature or workflow is added.

## 1. What this system is

This project is a Streamlit-based SCADA demand intelligence dashboard.

At a high level, it does six things:

1. Visualizes historical demand and generation patterns
2. Correlates demand with weather
3. Explains demand behavior through Agent Chat
4. Forecasts likely demand behavior
5. Monitors forecast quality and production health
6. Supports operational workflows such as operator briefings and scheduled snapshots

## 2. System architecture in plain language

The app follows a layered structure:

1. Data layer
- reads SCADA and weather data
- supports MongoDB or local fallback CSV files

2. Analytics layer
- computes KPIs, charts, anomalies, weather relationships, and forecasts

3. Production control layer
- validates data quality
- monitors forecast quality
- records forecast runs
- builds saved briefing history
- monitors scheduled job health

4. Interaction layer
- Streamlit pages
- Agent Chat
- operator-facing summaries

## 3. Main entrypoint

### [app.py](D:/Self_Learning/scada-agent-project%20-Anti_Gravity%20-%20Copy/scada-streamlit-public/app.py)

This is the main Streamlit application file.

It is responsible for:

- page navigation
- sidebar filters
- page rendering
- connecting the UI to utility modules

Important idea:

`app.py` should mostly coordinate, not do heavy logic directly. The detailed logic lives in `utils/`.

## 4. Sidebar behavior

The sidebar does three important jobs:

1. Navigation
- switches between pages

2. Global filters
- date range
- weekend exclusion
- holiday exclusion
- special event exclusion

3. Source transparency
- tells the user whether the app is using:
  - MongoDB
  - sample CSV fallback

These filters are stored in session state and reused across multiple pages.

## 5. Dashboard pages walkthrough

## 5.1 Overview

Purpose:

- quick system snapshot
- basic demand KPIs
- demand trend
- anomaly summary

Typical user:

- business reviewer
- first-time dashboard visitor
- operator wanting a top-level summary

Main outputs:

- KPI cards
- total daily demand trend
- daily peak/min/average
- anomaly chart
- short insight messages

## 5.2 Production Readiness

Purpose:

- explain the production roadmap
- show whether the system is trustworthy and operationally healthy

This is the page that moves the app beyond "just a dashboard."

Subsections:

### Roadmap

Explains the production plan in phases:

- Data Health and Forecast Monitoring
- Model Governance and Observability
- Automation and Daily Briefings
- Service Layer and Production Hardening

### Data Health

Explains and measures:

- block completeness
- duplicates
- incomplete days
- weather merge coverage
- missingness in key columns

Why it matters:

If the data is not reliable, downstream analytics also become less reliable.

### Forecast Monitoring

Explains and measures:

- average MAPE
- average MAE
- average peak error
- peak time hit rate
- recent backtest history

Why it matters:

This tells us whether the forecast model is stable or drifting.

### Version Comparison

Explains and measures:

- which forecast variant performs best on the same recent days
- how demand-only and weather-aware variants compare
- whether recent error is stable, improving, or worsening

Why it matters:

This is the simplest production-safe way to answer whether the current forecast version should still be trusted.

### Forecast Registry

Shows forecast run traceability:

- recent session forecast runs
- persisted forecast runs when enabled
- metadata such as:
  - model version
  - target date
  - weather signal
  - risk level

Why it matters:

This is the audit trail for forecast generation.

### Operator Briefing

Shows:

- current operator-style summary
- recent briefing history
- persisted briefing history when enabled

Why it matters:

This is the communication layer that translates forecast outputs into human-ready guidance.

### Scheduling

Explains:

- how the daily snapshot job should run
- what command should be scheduled
- whether the automation is healthy
- last run
- last success
- recent failures

Why it matters:

A production system must monitor the automation itself, not only the forecast outputs.

## 5.3 Regional Analysis

Purpose:

- understand regional demand contribution and trend

Typical user:

- grid analyst
- reviewer comparing zones

Main outputs:

- regional contribution
- regional trend
- regional variability

## 5.4 Generation Mix

Purpose:

- show thermal, hydel, and renewable generation composition over time

Typical user:

- operations planning
- reporting and review

## 5.5 Intraday Profile

Purpose:

- inspect one day at 96-block resolution

Main outputs:

- intraday curve
- ramp analysis
- intraday anomaly detection

Typical user:

- operator
- analyst looking for detailed daily behavior

## 5.6 Weather Correlation

Purpose:

- understand how weather relates to demand

This page has grown into one of the most analytically rich parts of the app.

Key sections:

- daily relationship
- intraday calendar
- date comparison
- quadrant analysis

Why it is important:

It connects historical demand behavior with weather behavior and supports both intuitive and analyst-level views.

## 5.7 Forecasting

Purpose:

- estimate expected demand shape
- identify likely peak window
- assess risk
- generate operator-ready summary

Forecast modes:

### Historical Backtest

Uses recent historical data to forecast a known day and compare forecast vs actual.

Why it exists:

- model evaluation
- reliability measurement

### Forward-Looking Open-Meteo

Uses Open-Meteo forecast weather plus historical demand patterns to produce a live-style outlook.

Why it exists:

- operational planning
- next-day-style preparedness

Important note:

The system warns when the live forecast month is outside the historical demand month pattern in the dataset.

### Forecast Governance section

This section explains:

- what forecast metadata is being logged
- whether persistence is enabled
- run ID and model version

### Operator Briefing section

This section gives the short operational message a shift lead would likely want first.

## 5.8 Agent Chat

Purpose:

- answer questions using the selected SCADA and weather data

This is not a general chatbot. It is constrained to the project data and deterministic tool context.

What it supports:

- summaries
- comparisons
- intraday analysis
- anomaly queries
- weather questions
- forecast outlook questions

Why it matters:

It acts as a natural-language interface on top of the analytical and forecast layers.

## 6. Utility modules walkthrough

## 6.1 [utils/data_loader.py](D:/Self_Learning/scada-agent-project%20-Anti_Gravity%20-%20Copy/scada-streamlit-public/utils/data_loader.py)

Purpose:

- load and normalize SCADA and weather data
- support MongoDB and local CSV fallback
- add calendar features

Key responsibility:

This module decides what data the rest of the system sees.

## 6.2 [utils/charts.py](D:/Self_Learning/scada-agent-project%20-Anti_Gravity%20-%20Copy/scada-streamlit-public/utils/charts.py)

Purpose:

- build Plotly charts used across the dashboard

Contains:

- trend charts
- anomaly charts
- weather charts
- comparison charts
- forecast charts

Key responsibility:

Visualization only. It should not become the main business-logic layer.

## 6.3 [utils/forecasting.py](D:/Self_Learning/scada-agent-project%20-Anti_Gravity%20-%20Copy/scada-streamlit-public/utils/forecasting.py)

Purpose:

- forecast demand using same-block historical behavior
- optionally adjust forecast using weather
- support:
  - historical backtest
  - forward Open-Meteo forecast mode

Key responsibility:

This is the core demand forecasting engine.

## 6.4 [utils/forecast_registry.py](D:/Self_Learning/scada-agent-project%20-Anti_Gravity%20-%20Copy/scada-streamlit-public/utils/forecast_registry.py)

Purpose:

- create structured forecast run records
- optionally persist them to MongoDB
- maintain recent forecast run history

Key responsibility:

Traceability and governance of forecast execution.

## 6.5 [utils/forecast_snapshot.py](D:/Self_Learning/scada-agent-project%20-Anti_Gravity%20-%20Copy/scada-streamlit-public/utils/forecast_snapshot.py)

Purpose:

- build one reusable daily forecast snapshot workflow

This is important because it allows the same logic to be used:

- interactively
- from scripts
- from future schedulers

## 6.6 [utils/operator_briefing.py](D:/Self_Learning/scada-agent-project%20-Anti_Gravity%20-%20Copy/scada-streamlit-public/utils/operator_briefing.py)

Purpose:

- convert forecast outputs into a deterministic operator summary

Why deterministic:

- stable
- easier to audit
- production-friendly

## 6.7 [utils/production_monitoring.py](D:/Self_Learning/scada-agent-project%20-Anti_Gravity%20-%20Copy/scada-streamlit-public/utils/production_monitoring.py)

Purpose:

- compute data health metrics
- compute forecast monitoring metrics
- compare forecast variants
- detect basic forecast drift

Key responsibility:

This module measures whether the production system is trustworthy.

## 6.8 [utils/execution_monitoring.py](D:/Self_Learning/scada-agent-project%20-Anti_Gravity%20-%20Copy/scada-streamlit-public/utils/execution_monitoring.py)

Purpose:

- track whether automation runs succeeded or failed
- provide execution-health summary

Key responsibility:

This module measures whether the automation itself is healthy.

## 6.9 [utils/agent_chat.py](D:/Self_Learning/scada-agent-project%20-Anti_Gravity%20-%20Copy/scada-streamlit-public/utils/agent_chat.py)

Purpose:

- provide chat behavior
- run deterministic local tools
- invoke Gemini
- connect to LangSmith tracing and feedback

Key responsibility:

Natural-language access to the data and analytics layers.

## 6.10 Other support modules

### [utils/kpi_cards.py](D:/Self_Learning/scada-agent-project%20-Anti_Gravity%20-%20Copy/scada-streamlit-public/utils/kpi_cards.py)

Renders top-level KPI cards used in the Overview page.

### [utils/insights.py](D:/Self_Learning/scada-agent-project%20-Anti_Gravity%20-%20Copy/scada-streamlit-public/utils/insights.py)

Provides short textual analytical insights for selected pages.

### [utils/ai_insights.py](D:/Self_Learning/scada-agent-project%20-Anti_Gravity%20-%20Copy/scada-streamlit-public/utils/ai_insights.py)

Older/support insight helpers used for summary logic.

## 7. Automation and scripts

## 7.1 [run_daily_forecast_snapshot.py](D:/Self_Learning/scada-agent-project%20-Anti_Gravity%20-%20Copy/scada-streamlit-public/scripts/run_daily_forecast_snapshot.py)

Purpose:

- generate the daily forecast snapshot outside Streamlit
- optionally persist:
  - forecast run
  - operator briefing
  - execution event

Why this matters:

This is the bridge from interactive dashboard to production workflow.

## 7.2 [upload_langsmith_dataset.py](D:/Self_Learning/scada-agent-project%20-Anti_Gravity%20-%20Copy/scada-streamlit-public/scripts/upload_langsmith_dataset.py)

Purpose:

- upload evaluation cases into LangSmith

Why it matters:

This supports evaluation discipline for Agent Chat behavior.

## 8. Secrets and configuration

The main optional secrets are:

- `GOOGLE_API_KEY`
- `LANGSMITH_API_KEY`
- `LANGSMITH_PROJECT`
- `LANGSMITH_TRACING`
- `LANGSMITH_ENDPOINT`
- `MONGODB_URI`
- `OPEN_METEO_LATITUDE`
- `OPEN_METEO_LONGITUDE`
- `OPEN_METEO_TIMEZONE`
- `ENABLE_FORECAST_RUN_LOGGING`

## 9. Current production maturity

At this stage, the system already includes:

- dashboard analytics
- weather-demand intelligence
- forecasting
- forecast monitoring
- forecast governance
- operator briefing
- scheduled snapshot workflow
- execution monitoring

This is already far beyond a simple demo dashboard.

## 10. How this documentation should be maintained

Whenever a major feature is added, update this guide in at least three places:

1. add the new page or workflow in the dashboard walkthrough
2. add or update the relevant utility module description
3. add the production significance of that feature

Recommended rule:

If the user can see a new major feature in the dashboard, this document should mention it.

If a new important utility module is introduced, this document should explain it.

## 11. Recommended next documentation habit

Whenever we add the next production feature, we should update:

- this walkthrough
- the roadmap document if the architecture changes
- the relevant feature-specific guide

That will keep the system understandable as it scales.
