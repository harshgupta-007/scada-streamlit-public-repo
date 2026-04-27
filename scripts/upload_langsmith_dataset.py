import argparse
import json
import os
from pathlib import Path

from langsmith import Client


DEFAULT_DATASET_NAME = "scada-agent-chat-evals"
DEFAULT_EVAL_FILE = Path("evals") / "agent_chat_eval_cases.json"


def load_eval_cases(eval_file: Path):
    with eval_file.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_client() -> Client:
    api_key = os.environ.get("LANGSMITH_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("LANGSMITH_API_KEY is not set in the environment.")

    api_url = os.environ.get("LANGSMITH_ENDPOINT", "").strip()
    if api_url:
        return Client(api_key=api_key, api_url=api_url)
    return Client(api_key=api_key)


def get_or_create_dataset(client: Client, dataset_name: str):
    matches = list(client.list_datasets(dataset_name=dataset_name))
    if matches:
        return matches[0]

    return client.create_dataset(
        dataset_name=dataset_name,
        description="Standard evaluation prompts for the SCADA public Streamlit Agent Chat.",
    )


def existing_case_ids(client: Client, dataset_id) -> set:
    existing = set()
    for example in client.list_examples(dataset_id=dataset_id):
        metadata = getattr(example, "metadata", {}) or {}
        case_id = metadata.get("case_id")
        if case_id:
            existing.add(case_id)
    return existing


def upload_cases(client: Client, dataset_id, cases, replace_existing: bool = False):
    existing = existing_case_ids(client, dataset_id)
    inputs = []
    outputs = []
    metadata = []

    for case in cases:
        case_id = case["id"]
        if case_id in existing and not replace_existing:
            continue

        inputs.append({"prompt": case["prompt"]})
        outputs.append(
            {
                "expected_scope": case["expected_scope"],
                "checks": case["checks"],
            }
        )
        metadata.append(
            {
                "case_id": case_id,
                "category": case["category"],
            }
        )

    if not inputs:
        return 0

    client.create_examples(
        inputs=inputs,
        outputs=outputs,
        metadata=metadata,
        dataset_id=dataset_id,
    )
    return len(inputs)


def main():
    parser = argparse.ArgumentParser(description="Upload SCADA Agent Chat evaluation cases to LangSmith.")
    parser.add_argument(
        "--dataset-name",
        default=DEFAULT_DATASET_NAME,
        help=f"LangSmith dataset name. Default: {DEFAULT_DATASET_NAME}",
    )
    parser.add_argument(
        "--eval-file",
        default=str(DEFAULT_EVAL_FILE),
        help=f"Path to the local evaluation JSON file. Default: {DEFAULT_EVAL_FILE}",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Upload all cases even if a case_id already exists in the dataset.",
    )
    args = parser.parse_args()

    eval_file = Path(args.eval_file)
    if not eval_file.exists():
        raise FileNotFoundError(f"Evaluation file not found: {eval_file}")

    client = get_client()
    dataset = get_or_create_dataset(client, args.dataset_name)
    cases = load_eval_cases(eval_file)
    uploaded = upload_cases(client, dataset.id, cases, replace_existing=args.replace_existing)

    print(f"Dataset: {dataset.name}")
    print(f"Dataset ID: {dataset.id}")
    print(f"Cases in file: {len(cases)}")
    print(f"Cases uploaded in this run: {uploaded}")


if __name__ == "__main__":
    main()
