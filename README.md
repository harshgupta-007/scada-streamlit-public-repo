# SCADA Demand Dashboard

A public, Streamlit-based dashboard for exploring SCADA demand patterns using a safe sample dataset.

This repository is being prepared for deployment on Streamlit Cloud with a security-first, public-repo-friendly setup.

## Phase 1 Scope

This first public release includes:

- Overview dashboard
- Regional analysis
- Generation mix analysis
- Intraday profile analysis
- sample-data-only operation

Deferred for a later secure phase:

- agent chat
- weather correlation backed by private data services
- external database integrations

## Why this repo is structured this way

This project is being prepared for a public GitHub repository, so the deployment version must:

- contain no secrets or credentials
- avoid private or oversized datasets
- stay comfortably below GitHub's 100 MB file limit
- run cleanly on Streamlit Cloud

## Project structure

- `app.py`: Streamlit app entrypoint
- `utils/`: charting, data loading, KPI, and insight helpers
- `data/`: approved public sample dataset
- `assets/`: approved static assets used by the UI
- `.streamlit/`: Streamlit configuration
- `docs/`: migration, deployment, and review notes

## Local run

Create a virtual environment, install dependencies, and run:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment approach

The deployment flow for this project is:

1. Review all files in this clean public workspace.
2. Push only this reviewed workspace to a new public GitHub repository.
3. Connect that repository to Streamlit Cloud.
4. Configure any future secrets only in Streamlit Cloud settings.
5. Deploy and validate the app.

Detailed deployment notes are available in:

- `docs/STREAMLIT_CLOUD_DEPLOYMENT.md`
- `docs/DEPLOYMENT_WALKTHROUGH.md`
- `docs/REVIEW_CHECKLIST.md`

## Security rules for this repo

- Never commit `.env` or secrets.
- Never commit private keys.
- Never commit local DB files.
- Never commit raw private operational datasets.
- Keep optional backend features disabled until they are ready for secure cloud deployment.

## Current dataset

The current app uses the sample file in `data/sample_scada.csv`.

This is intentional for the first public deployment and keeps the app portable and safe for GitHub + Streamlit Cloud.
