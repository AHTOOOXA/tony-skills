# pishi — benchmark

Six tasks on fictional data (rental platform «Domly»): ops instruction, CTO
status, «объясни по-русски», family how-to, cut-a-bloated-draft, PR body in RU.
Prompts, expected output, judgment assertions and mechanical `checks` are in
`evals.json`; inputs in `inputs/`.

## Run one task by hand

```bash
cd pishi/evals
claude -p "$(jq -r '.evals[1].prompt' evals.json)"        # with the skill installed
```

For a baseline, run the same prompt from a directory where the skill is not
installed (or tell Claude not to use skills).

## Grade

```bash
python3 grade.py <run_dir> --eval 2      # <run_dir>/outputs/<file> → <run_dir>/grading.json
```

Mechanical checks (length, score, required / forbidden strings, numbers not in
the source, greeting, headers) are pass/fail from `scripts/check.py`. Judgment
assertions are copied with `passed: null` for a reader to fill in.

## Layout for A/B runs

```
<workspace>/iteration-1/eval-<id>-<name>/{with_skill,without_skill}/run-1/
    outputs/<file>   grading.json   timing.json
```

That is the layout Anthropic's `skill-creator` aggregator and viewer expect.

## Your own tasks

Copy this folder next to the skill (outside any public repo), replace inputs
with your real drafts, reports and tickets, and keep the ground-truth texts you
already accepted as `references/` — they are the best possible expected output.
