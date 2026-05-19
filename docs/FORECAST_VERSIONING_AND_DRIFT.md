# Forecast Version Comparison and Drift Analysis

This guide explains the new production feature that compares forecast variants side by side and checks whether forecast quality is drifting over time.

## Why this feature exists

Forecasting in production should answer two separate questions:

1. Which forecast version is currently the strongest?
2. Is that forecast version staying stable over time?

Without these checks, a system can look healthy while forecast quality quietly degrades.

## Where this appears in the dashboard

Open:

- `Production Readiness`
- `Version Comparison`

This tab is the model-governance layer for forecasting.

## Forecast variants currently compared

The dashboard currently evaluates three forecast variants on the same recent historical days:

1. `Demand Only Baseline`
- Uses same-block demand history only
- No weather adjustment

2. `Weather-Aware Apparent Temperature`
- Uses apparent temperature to adjust the same-block baseline

3. `Weather-Aware Temperature`
- Uses air temperature to adjust the same-block baseline

These variants are intentionally simple and interpretable. The goal at this stage is not model complexity. The goal is operational comparability and traceability.

## Mathematics behind the comparison

For each variant and each evaluation day:

1. Take the selected target day
2. Use the previous selected lookback days as history
3. Build a forecast for all `96` blocks
4. Compare forecast vs actual

The same target dates are used across all variants, so the comparison is fair.

### Demand-only baseline

For each block `b`:

`forecast_b = mean(history demand at block b)`

### Weather-aware variant

For each block `b`:

1. compute historical block demand mean
2. compute historical block weather mean
3. compute weather beta

`beta_b = cov(weather_b, demand_b) / var(weather_b)`

Then:

`forecast_b = demand_mean_b + beta_b * (target_weather_b - history_weather_mean_b)`

This lets weather shift the baseline up or down.

## Metrics used

### Average MAPE

Mean Absolute Percentage Error across the recent evaluation window.

Why it matters:
- gives a simple percentage accuracy measure
- lower is better

### Average MAE

Mean Absolute Error in MW.

Why it matters:
- easier to interpret operationally than percentage alone

### Average Peak Error

Absolute difference between predicted and actual daily peak MW.

Why it matters:
- peak accuracy is often more important operationally than average accuracy

### Peak Time Hit Rate

How often the predicted peak time exactly matched the actual peak time.

Why it matters:
- peak timing supports staffing, balancing, and operational readiness

## What drift analysis means

Drift analysis checks whether recent forecast error is changing over time.

The current implementation splits the evaluation window into:

- early window
- recent window

Then it compares:

`MAPE shift = recent_window_mape - early_window_mape`

### Interpretation

- Positive shift:
  recent error is worse than earlier error
- Negative shift:
  recent error is better than earlier error
- Near zero:
  performance is broadly stable

### Current status labels

- `Improving`
- `Stable`
- `Worsening`

The current thresholds are intentionally simple:

- `Worsening` if shift is `>= 0.5` percentage points
- `Improving` if shift is `<= -0.5` percentage points
- otherwise `Stable`

## How to read the Version Comparison tab

### 1. Current Best Variant card

This shows the recent winner across the selected backtest window.

It answers:
- which variant is best right now?

### 2. Average Error by Variant chart

This helps compare the average forecast error of each model version.

It answers:
- which version is strongest overall?

### 3. MAPE by Day chart

This shows daily error lines for each variant.

It answers:
- are some variants unstable on specific days?
- is one variant consistently better?

### 4. Early vs Recent Drift chart

This compares each variant’s earlier-window vs recent-window MAPE.

It answers:
- is any model getting worse recently?

### 5. Tables

These provide:
- exact summary metrics
- exact drift values
- per-day comparison rows

## Why this is production-relevant

This feature makes the forecast layer more production-grade because it adds:

- model comparison
- recent performance validation
- simple drift detection
- a documented basis for choosing the active forecast version

## Current limitation

This is not yet a full MLOps platform.

Current limits:

- comparison is based on recent backtest windows only
- drift is based on simple earlier-vs-recent window logic
- no automated champion/challenger rollout exists yet

These are good constraints for the current stage because the system remains interpretable and easy to audit.

## Recommended next step after this feature

The natural next evolution is:

1. persist version-comparison results
2. compare production runs against a named champion model
3. detect drift automatically from saved historical runs
4. alert when the active version is no longer the best recent performer
