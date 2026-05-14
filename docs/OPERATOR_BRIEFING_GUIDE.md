# Operator Briefing Guide

This document explains the operator briefing layer added on top of the forecasting system.

## Why this layer exists

Production systems should not require every operator to interpret several charts before understanding the forecast situation.

An operator briefing is meant to answer, quickly:

- what demand shape is expected
- when the likely peak window is
- how serious the current risk level is
- what reliability caveats exist

This is the communication layer built on top of the forecast and governance layers.

## Design principle

The briefing is intentionally deterministic.

That means it is built directly from:

- forecast summary fields
- risk cards
- risk flags
- reliability warnings

It does **not** depend on free-form LLM generation. That makes it:

- stable
- auditable
- easier to trust in operational use

## What the briefing contains

Each generated briefing has:

1. Headline
- a short title like:
  - `2026-05-15 Forward Outlook: Moderate operational risk`

2. Briefing text
- compact narrative summary covering:
  - expected peak MW
  - expected peak window
  - expected daily energy
  - operational tone
  - reliability note
  - weather context when available

3. Sectioned breakdown
- `Expected Operating Shape`
- `Risk View`
- `Operational Watchpoints`
- `Reliability Note`
- `Weather Context` when applicable

## Where it appears

### Forecasting page

The briefing appears directly after forecast governance and before the full risk-detail view.

This is the best place for:

- daily operational reading
- shift handover discussion
- management summary before deeper chart inspection

### Production Readiness > Operator Briefing

This tab shows the latest generated briefing from the current session.

Its purpose is to help users understand that:

- the briefing is part of the production communication workflow
- it is derived from controlled forecast outputs
- it can later be automated into a scheduled daily summary

## How to interpret it as a learner

Think of the stack like this:

1. Forecast model
- predicts demand behavior

2. Monitoring and governance
- measures whether the system is reliable and traceable

3. Operator briefing
- translates those outputs into a short actionable message

This is how production systems become usable by real people, not only analysts.

## Relationship to forecast governance

The operator briefing is also stored inside the forecast run record.

That means a saved run can later answer:

- what was forecast
- how risky it looked
- how the system summarized it for operators at that time

This is valuable for:

- incident review
- model comparison
- operational audit trails

## Recommended next step

The strongest next production step after this is:

1. daily scheduled forecast run
2. automatic operator briefing generation
3. stored forecast briefing history

At that point, the app moves from “dashboard with forecasts” to “operational forecast workflow.”
