# LangSmith Dataset Upload

This project keeps the standard Agent Chat evaluation prompts in:

- `evals/agent_chat_eval_cases.json`

You can upload them into LangSmith as a reusable dataset with:

- `scripts/upload_langsmith_dataset.py`

## What this does

- Creates a LangSmith dataset if it does not already exist
- Uploads each eval case as a dataset example
- Stores:
  - `prompt` as the input
  - `expected_scope` and `checks` as the reference output
  - `case_id` and `category` as metadata

## Local prerequisites

Set these environment variables in your terminal before running the script:

```powershell
$env:LANGSMITH_API_KEY="your_langsmith_api_key"
$env:LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
```

`LANGSMITH_ENDPOINT` is optional if you use the default hosted endpoint.

## Upload command

From the repo root, run:

```powershell
python scripts/upload_langsmith_dataset.py --dataset-name "scada-agent-chat-evals"
```

## Re-upload behavior

By default, the script skips eval cases whose `case_id` already exists in the dataset.

If you intentionally want to upload all current file cases again, use:

```powershell
python scripts/upload_langsmith_dataset.py --dataset-name "scada-agent-chat-evals" --replace-existing
```

## Recommended dataset name

Use:

- `scada-agent-chat-evals`

This keeps the LangSmith dataset separate from the tracing project:

- tracing project: `SCADA Demand Intelligence Dashboard`
- eval dataset: `scada-agent-chat-evals`

## After upload

In LangSmith:

1. Open Datasets
2. Open `scada-agent-chat-evals`
3. Verify each example shows:
   - prompt input
   - expected scope and checks
   - metadata with `case_id` and `category`
