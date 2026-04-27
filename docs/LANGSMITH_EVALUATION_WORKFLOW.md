# LangSmith Evaluation Workflow

This project uses LangSmith in three layers:

1. Agent Chat trace logging
2. User feedback on the latest response
3. Standard evaluation prompts for repeatable review

## Goal

After each meaningful Agent Chat or weather-analysis change, run the same evaluation prompts so answer quality stays stable over time.

## Evaluation source

Use:

- `evals/agent_chat_eval_cases.json`

Each case contains:

- `id`: stable identifier
- `category`: type of question
- `prompt`: question to ask in Agent Chat
- `expected_scope`: what date/range behavior should happen
- `checks`: plain-language review criteria

## Recommended review flow

1. Deploy or run the updated app locally.
2. Open Agent Chat.
3. Ask each prompt from `evals/agent_chat_eval_cases.json`.
4. Open the matching traces in LangSmith.
5. Review:
   - output quality
   - tool usage
   - trace metadata
   - user feedback if submitted

## What good looks like

- Answers stay grounded in the public sample dataset.
- Date scoping is correct and explicit.
- Units remain correct:
  - MW for power
  - GWh for energy
- Weather questions mention relationship or correlation carefully.
- Missing dates do not produce fabricated outputs.
- No trace includes secrets or hidden/private data.

## Suggested manual checklist

- Is the response numerically plausible?
- Does the response match the selected date scope?
- Does the response use the deterministic tool results?
- Does the response avoid overclaiming causation?
- Does the trace metadata make filtering easy later?

## Suggested trace filters in LangSmith

Filter by metadata when reviewing:

- `prompt_type`
- `start_date`
- `end_date`
- `selected_weather_variable`
- `weather_enabled`

## Minimum regression set

At minimum, review these 5 prompt types after major changes:

1. monthly summary
2. date comparison
3. intraday weather analysis
4. anomaly question
5. missing-date guardrail
