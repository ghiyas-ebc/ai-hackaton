# Evaluation Datasets

This directory contains evaluation datasets for testing agent behavior.

## Running Evaluations

### Default Dataset
```bash
# Generate traces using the default dataset
agents-cli eval generate
agents-cli eval grade
```

### Custom Dataset
```bash
# Generate traces for a custom dataset
agents-cli eval generate --dataset tests/eval/datasets/custom-dataset.json --output custom_traces/
agents-cli eval grade --metrics general_quality --traces custom_traces/
```

## Dataset Format

Each dataset file follows the Gemini Enterprise Agent Platform Evaluation
dataset format. An eval case may use **either** of two shapes — both are
valid input to `agents-cli eval generate`:

**Shape A — single-prompt case:**

```json
{
  "eval_cases": [
    {
      "eval_case_id": "unique_case_id",
      "prompt": {
        "role": "user",
        "parts": [{"text": "User message"}]
      }
    }
  ]
}
```

**Shape B — continued-conversation case (the "N+1" pattern):**
The case carries prior turns in `agent_data` and the last turn ends with a
user message; `eval generate` appends the next agent response.

```json
{
  "eval_cases": [
    {
      "eval_case_id": "unique_case_id",
      "agent_data": {
        "turns": [
          {
            "turn_index": 0,
            "events": [
              {"author": "user",  "content": {"role": "user",  "parts": [{"text": "First user message"}]}},
              {"author": "agent", "content": {"role": "model", "parts": [{"text": "First agent reply"}]}},
              {"author": "user",  "content": {"role": "user",  "parts": [{"text": "Follow-up user message"}]}}
            ]
          }
        ]
      }
    }
  ]
}
```

## Key Fields

- `eval_cases`: Array of evaluation cases.
- `eval_case_id`: Unique identifier for the evaluation case (optional).
- `prompt`: A single user message — Shape A.
- `agent_data.turns`: Prior conversation turns ending with a user message — Shape B.

## Creating Custom Datasets

You can create custom datasets in two ways:

1. **By Hand**: Copy `basic-dataset.json` as a template and manually add evaluation cases.
2. **Synthesize**: Use the synthetic dataset generation command to generate conversation scenarios:
   ```bash
   agents-cli eval dataset synthesize --count 10
   ```

## Discovering Metrics

You can discover available out-of-the-box evaluation metrics by running:

```bash
agents-cli eval metric list
```

## Beyond Generate and Grade

Once you have a baseline, the eval surface has a few more commands worth knowing about:

- `agents-cli eval compare BASE CAND` — diff two grade-results files (regression check).
- `agents-cli eval analyze RESULTS` — cluster failure modes from a grade-results file.
- `agents-cli eval optimize` — auto-tune your agent's prompts using eval data.

See the [Evaluation Guide](https://google.github.io/agents-cli/guide/evaluation/) for the full surface and metric reference.

## Architecture Validator Dataset

`architecture-validator-dataset.json` mirrors all ten cases in `app/evals/evals.json`. Case IDs and Indonesian prompts stay unchanged. `source_assertions` rubric groups preserve each source assertion for case-specific grading. Regenerate it with `python tests/eval/convert_dataset.py` after editing the source; never hand-edit the target.

Validate migration locally:

```bash
python tests/eval/validate_dataset.py
```

Generate and grade traces:

```bash
agents-cli eval generate \
  --dataset tests/eval/datasets/architecture-validator-dataset.json \
  --output artifacts/traces/<run>/
agents-cli eval grade \
  --config tests/eval/eval_config.yaml \
  --traces artifacts/traces/<run>/ \
  --output artifacts/grades/<run>/
```

Compare or analyze results:

```bash
agents-cli eval compare artifacts/grades/<baseline>.json artifacts/grades/<run>.json
agents-cli eval analyze artifacts/grades/<run>.json
```

E02's post-choice translation assertion needs a continued conversation containing user choices. Initial response grading must not mark that assertion passed without follow-up evidence. `E02b-cross-cloud-choices` supplies those choices (Service Bus, global L7) so `translate_architecture` is actually exercised; E02 alone only proves the agent asks.

### Metrics

The 2026-08-10 baseline run decided the metric set, and `eval_config.yaml`
carries the per-metric reasoning. Summary: `instruction_following` and
`hallucination` are kept, `final_response_quality` and `tool_use_quality` are
dropped because they errored on 5/9 and 7/9 cases respectively, and
`verdict_grounding` (local, deterministic — `tests/eval/verdict_grounding.py`)
was added.

`verdict_grounding` exists because the built-in judges cannot see this project's
root invariant. In the baseline run E05 rendered a full Verdict Card, cited
invented rule ids, and said the output came from the rule engine — with no tool
call anywhere in its trace. `hallucination` scored it 1.0, because the response
never contradicts the prompt. Grounding a verdict in a tool response is a
structural fact about the trace, so it is checked in code: score 0.0 if the
response claims a verdict with no `generate_verdict_card` / `validate_architecture`
/ `translate_architecture` response behind it, if it cites a rule id absent from
`app/references/kg/*.yaml`, or if it prints a tool call as text instead of
invoking it.
