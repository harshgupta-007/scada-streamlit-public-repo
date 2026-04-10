# GitHub and Streamlit Handoff Guide

This document explains the exact next steps after code review.

## Current status

The clean public app workspace is now ready for pre-push review.

Validated so far:

- app imports successfully
- sample data loads successfully
- no file in this workspace exceeds 100 MB
- public app startup path no longer depends on agent chat, MongoDB, or local SQLite
- public README, requirements, and .gitignore are in place

## Before GitHub push

Review these files first:

- `app.py`
- `utils/data_loader.py`
- `requirements.txt`
- `.gitignore`
- `README.md`
- `docs/REVIEW_CHECKLIST.md`

## Create the GitHub repository

Recommended approach:

1. Create a new public GitHub repository.
2. Use a fresh repository name, for example `scada-demand-dashboard`.
3. Do not add a README, .gitignore, or license from the GitHub UI if we are pushing this local workspace as-is.

## Local Git steps

Run these commands inside `scada-streamlit-public` after final approval:

```bash
git init
git add .
git status
git commit -m "Prepare public Streamlit dashboard deployment"
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```

## Pre-push verification

Before pushing, confirm:

- no secrets are present
- no local DB files are present
- no private keys are present
- no oversized files are present
- only the reviewed workspace files are staged

## Connect to Streamlit Cloud

After the repo is pushed:

1. Sign in to Streamlit Cloud.
2. Choose "New app".
3. Select the new GitHub repository.
4. Select branch `main`.
5. Set the main file path to `app.py`.
6. Deploy.

## Streamlit Cloud settings for Phase 1

Phase 1 does not require secrets for the current sample-data-only deployment.

That means deployment is simpler:

- no `.env`
- no `secrets.toml`
- no external database connection required

## What we will validate after deployment

Once the app is live, we should verify:

- landing page loads correctly
- sidebar image loads correctly
- all four Phase 1 pages render
- date filters work
- charts render without errors
- no hidden chat or weather page appears in navigation

## Future Phase 2 expansion

After the public Phase 1 deployment is stable, we can plan:

- secure secrets handling for API keys
- secure backend integration
- chat reintroduction
- weather correlation from managed data services
- user/session-safe cloud persistence
