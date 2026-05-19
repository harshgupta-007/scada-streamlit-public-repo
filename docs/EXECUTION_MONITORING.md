# Execution Monitoring

This document explains the scheduled-job health monitoring layer added on top of the forecast automation workflow.

## Why this layer matters

Once a system is automated, we need to know more than whether forecasts exist.

We also need to know:

- did the scheduled job actually run
- did it succeed or fail
- when was the last successful execution
- are there recent failures
- is the automation stale

This is what execution monitoring provides.

## What is now implemented

The project now records execution events for the daily snapshot job.

### Execution event fields

Each execution event can capture:

- `execution_id`
- `job_name`
- `status`
- `started_at_utc`
- `ended_at_utc`
- `duration_seconds`
- `message`
- `error_message`
- `run_id` when available
- `mode` when available
- `target_date` when available
- `overall_risk_level` when available
- `operator_headline` when available

## Execution statuses

### `success`

The scheduled job completed and generated a forecast snapshot successfully.

### `failure`

The scheduled job failed and captured the error reason when possible.

## Where events are stored

When forecast run logging is enabled, execution events are written to:

- `SCADA_AGENT.Forecast_job_executions`

This uses the same opt-in persistence model as forecast run logging.

## Dashboard view

Inside `Production Readiness > Scheduling`, the dashboard now shows:

- automation health card
- last run time
- last success time
- recent failure count
- recent execution event table

## How automation health is interpreted

### Low

- latest execution succeeded
- and it happened within the expected time window

### Moderate

- no recent failure
- but the automation appears stale because no recent run was recorded

### High

- the latest execution failed

## Why this is useful

This closes the production loop:

1. forecast model runs
2. forecast outputs are stored
3. operator briefing is generated
4. execution health itself is monitored

Without this step, a system may look healthy while the scheduled job has silently stopped running.

## Recommended next step

The strongest next production step is:

1. extend observability to forecast job traces and failure categories
2. optionally send failure alerts
3. add model/version comparison workflow

That would turn the system from production-capable into operationally mature.
