# Deployment Walkthrough

This walkthrough explains what will happen from local review to Streamlit Cloud deployment.

## Stage 1: Build the clean public app locally

What we do:

- work only inside the clean `scada-streamlit-public` folder
- copy the approved Phase 1 files
- refactor them for public deployment
- test locally

What you review:

- every file copied into the new workspace
- every code change made after copy
- the dependency list
- the deployment settings and documentation

## Stage 2: Prepare the GitHub repository

What we do:

- ensure the public folder contains only approved content
- check that no file exceeds 100 MB
- add a strict `.gitignore`
- create a clean commit history for the deployable app

What you review:

- final file tree
- final diff
- final README and docs

## Stage 3: Push to GitHub

What we do:

- create a new public GitHub repo
- connect the local public workspace to that repo
- push only the deployment workspace

Important rule:

- after a secret or private file is pushed to a public repo, removing it later is not enough on its own
- that is why we are doing the clean-folder workflow first

## Stage 4: Connect to Streamlit Cloud

What we do in Streamlit Cloud:

1. Sign in with GitHub.
2. Create a new app.
3. Select the repository.
4. Select the branch.
5. Set the app entry file.
6. Add secrets in the app settings if needed.
7. Deploy.

## Stage 5: First deployment checks

After deployment we verify:

- the app starts successfully
- the correct pages appear
- sample data loads correctly
- no missing package errors occur
- hidden features remain hidden when disabled
- assets resolve correctly

## Stage 6: Update cycle after deployment

For future changes:

1. Make changes locally in the clean workspace.
2. Review the diff.
3. Commit and push.
4. Streamlit Cloud auto-redeploys.
5. Validate the live app after deployment.

## Streamlit secrets concept

Public GitHub repo:

- visible to everyone
- should never contain real credentials

Streamlit secrets:

- stored in Streamlit Cloud app settings
- injected only at runtime
- used for API keys, database URIs, and other private configuration

## Why we are not pushing the old folder directly

The original project contains:

- private key material
- local database files
- local environment files
- large data files
- code paths designed for local development

Using a fresh folder reduces the chance of accidental exposure and makes deployment far easier to review.
