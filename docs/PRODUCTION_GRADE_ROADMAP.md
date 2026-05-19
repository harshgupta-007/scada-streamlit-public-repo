# Production-Grade Roadmap

This document explains how the SCADA dashboard evolves from a useful analytics app into a production-grade decision-support system.

## Why this roadmap exists

A production system is not defined only by features. It is defined by:

- trustworthy input data
- measurable model quality
- controlled failure behavior
- observability and traceability
- repeatable operations
- clear documentation for reviewers and operators

That is why we are building this in phases instead of adding isolated AI features.

## Phase 1: Data Health and Forecast Monitoring

This is the first and most important production layer.

### Objective

Make the current system trustworthy before adding more automation or intelligence.

### What is implemented

- `Production Readiness` page in the dashboard
- roadmap tab for learning and orientation
- `Data Health` tab
- `Forecast Monitoring` tab

### What Data Health checks

These checks answer whether the dashboard is reading usable operational data.

1. Block completeness
- Every day should ideally have all `96` quarter-hour blocks.
- Missing blocks can distort intraday curves, anomaly detection, weather analysis, and forecasts.

2. Duplicate date-block rows
- A `(date, block_no)` pair should normally appear once.
- Duplicates can corrupt aggregation and forecasting logic.

3. Incomplete days
- A day with fewer than `96` blocks is flagged.
- This is an early warning for ingestion or source-data issues.

4. Weather merge coverage
- Measures how much SCADA data is successfully matched with weather rows.
- Low coverage weakens weather correlation and weather-aware forecasting.

5. Key column missingness
- Shows missing-value percentages for important columns such as:
  - `demand_energy`
  - `thermal_gen`
  - `hydel_gen`
  - `renewable_gen`
  - `Raw_Freq`

### What Forecast Monitoring means

Forecast monitoring means:

- take recent historical days
- pretend each day is unknown
- forecast it using the previous selected days
- compare forecast vs actual

This is a backtest. It tells us whether the model is staying reliable.

### Metrics shown

1. Average MAPE
- Mean Absolute Percentage Error
- A quick view of average proportional forecast error

2. Average MAE
- Mean Absolute Error in MW
- Easier to interpret operationally than percentage alone

3. Average peak error
- How far predicted peak MW is from actual peak MW

4. Peak time hit rate
- How often the predicted peak time exactly matches the actual peak time

5. Daily forecast run table
- Gives per-day transparency instead of only a single summary metric

### Why this phase comes first

If data quality is poor or forecast error is drifting, then:

- AI explanations become less trustworthy
- anomaly interpretation becomes weaker
- next-day operational guidance becomes risky

So this phase creates the control layer needed for safe scaling.

## Phase 2: Model Governance and Observability

### Objective

Make every forecast explainable, versioned, and traceable.

### Planned work

- add model version metadata
- compare forecast variants on the same recent evaluation days
- detect drift by comparing earlier-window vs recent-window error
- log selected weather variable and lookback window
- log forward-vs-backtest mode
- track fallback reasons
- extend observability beyond Agent Chat into forecast execution

### What is now implemented in this phase

- forecast run metadata and governance
- operator briefing generation
- execution monitoring for scheduled runs
- forecast version comparison
- forecast drift analysis

### Why it matters

If a forecast becomes worse, the team should know:

- which model version produced it
- which inputs were used
- whether it was a fallback run
- what weather source was active

## Phase 3: Automation and Daily Briefings

### Objective

Move from manual dashboard usage to scheduled operational support.

### Planned work

- scheduled daily forecast generation
- daily saved forecast record
- short operator summary generation
- alert-oriented daily status output

### Why it matters

Operations teams benefit more from:

- a forecast prepared ahead of time
- a short briefing
- stable daily workflow

than from ad hoc manual chart inspection only.

## Phase 4: Service Layer and Production Hardening

### Objective

Separate concerns and make the system easier to scale.

### Planned work

- keep Streamlit as presentation layer
- move data prep into reusable pipeline modules
- move forecast execution into service-style functions/jobs
- define stronger deployment and retry behavior
- harden secret and network handling

### Why it matters

This reduces fragility and makes the system easier to:

- test
- audit
- secure
- extend

## Open-Meteo forward forecast note

The system now supports a forward-looking mode using the free Open-Meteo forecast API.

However, the current historical demand dataset appears to be centered on `November 2025`, while a live Open-Meteo forecast will be for the current calendar period.

Because of that, the dashboard now shows a reliability warning when:

- the forecast target month is outside the historical demand month pattern

This is an honest production behavior. It avoids giving a false impression of confidence.

## How to read the dashboard as a learner

### Production Readiness > Roadmap

Use this to understand:

- why production systems are layered
- why data quality comes before advanced AI

### Production Readiness > Data Health

Use this to understand:

- whether the input data is safe to trust
- what kinds of source-data issues can affect analytics

### Production Readiness > Forecast Monitoring

Use this to understand:

- whether forecast quality is stable
- which metrics actually matter operationally
- how to detect model drift early

### Production Readiness > Version Comparison

Use this to understand:

- which forecast variant is currently strongest
- whether the recent winner is stable
- whether a demand-only or weather-aware setup is performing better
- whether forecast quality is worsening in the recent window

## Recommended next implementation after Phase 1

The strongest next step is:

1. persist forecast run records
2. log model metadata and fallback causes
3. generate daily operator briefing

That will complete the transition from dashboard feature set to production workflow.
