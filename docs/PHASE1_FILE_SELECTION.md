# Phase 1 File Selection

This document proposes the exact files and folders to copy into the public deployment workspace for the first Streamlit Cloud release.

The goal is to create a public, reviewable, cloud-safe app that is small, secure, and easy to deploy.

## Phase 1 release goal

Deploy a dashboard-first version of the SCADA app using safe sample data.

Included in Phase 1:

- Overview
- Regional Analysis
- Generation Mix
- Intraday Profile

Deferred or feature-flagged for later:

- Agent Chat
- Weather Correlation if it requires private MongoDB-backed data

## Proposed files to copy

### Application code

Copy and then refactor:

- `app.py`
- `utils/charts.py`
- `utils/data_loader.py`
- `utils/insights.py`
- `utils/kpi_cards.py`
- `utils/ai_insights.py`

Why:

- These power the main dashboard pages.
- They can be adapted to a safe local sample-data mode.
- They are the smallest path to a working Streamlit Cloud deployment.

### Static assets

Copy:

- `Images/scada_architecture.png`

Why:

- This is the only image directly referenced by the current Streamlit UI sidebar.

Optional later review:

- any additional image only if it is truly used by the public app

### Data

Copy:

- `sample_scada.csv`

Why:

- It is small enough for a public repository.
- It gives us a safe local dataset for initial deployment.

## Proposed files not to copy in Phase 1

### Agent package

Do not copy initially:

- `scada_summary_agent/`

Why:

- The current `app.py` imports the agent package at module load time.
- That package brings in Google ADK, model config, session persistence, and chat-specific complexity.
- Phase 1 will be much safer and easier to review if the public app is dashboard-first.

When to include later:

- after we redesign chat for Streamlit Cloud
- after secrets are handled cleanly
- after session behavior is made safe for public multi-user use

### Weather and database setup scripts

Do not copy initially:

- `scripts/aggregate_weather_db.py`
- `scripts/init_events_db.py`

Why:

- These are backend data-prep scripts, not public app runtime files.
- They appear tied to MongoDB-backed flows.

### Tests

Do not copy the current test immediately:

- `tests/test_scada_agent.py`

Why:

- It targets the agent path, not the dashboard-first public deployment target.
- We can create a smaller safe smoke test later.

### Private, local, generated, or oversized artifacts

Do not copy:

- `.env`
- `.venv/`
- `.vscode/`
- `%USERPROFILE%/`
- `*.db`
- `*.log`
- `*.ipynb`
- `id_ed25519_personal`
- `id_ed25519_personal.pub`
- `admin.All_India_IBM_Weather_96_RTM.json`
- `admin.MP_Scada_Demand_new.json`
- `mp_scada_data.electricity_readings_old_bkp.json`
- `sample_scada_old.csv`
- `SCADA_AI_Agent_Report.pptx`
- `SCADA_AI_Agent_Documentation.pdf`

## Expected refactors after copying

Once copied, we should refactor these items before GitHub push:

1. Remove top-level imports that force agent/chat dependencies.
2. Add a config module for Streamlit secrets and feature flags.
3. Make `data_loader.py` work cleanly in sample-data mode by default.
4. Hide or remove pages that are not safe for Phase 1.
5. Clean up dependency declarations.

## Resulting Phase 1 public structure

Expected structure after copy and refactor:

```text
scada-streamlit-public/
  app.py
  requirements.txt
  .gitignore
  .streamlit/
    config.toml
  assets/
    scada_architecture.png
  data/
    sample_scada.csv
  utils/
    charts.py
    data_loader.py
    insights.py
    kpi_cards.py
    ai_insights.py
  docs/
    ...
```

## Why this is the professional choice

- Small enough for a public repository
- Safe enough for review before publication
- Clear separation between deployable app and private development artifacts
- Easier to debug on Streamlit Cloud
- Leaves room for a controlled Phase 2 backend-enabled release
