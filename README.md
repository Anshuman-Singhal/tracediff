# tracediff

> Regression testing for AI agents. Change a prompt, swap a model, add a tool: tracediff shows exactly what changed in agent behavior.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![Tests](https://img.shields.io/badge/tests-16%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Example output](#example-output)
- [How it works](#how-it-works)
- [Check types](#check-types)
- [CI usage](#ci-usage)
- [Bring your own agent](#bring-your-own-agent)
- [Project structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

## Features

- Runs a task suite against two agent versions and diffs the results
- Deterministic checks encode real business policy (refund eligibility, verification ordering), not string matching
- Reports regressions, improvements, trajectory changes, and token/latency deltas
- Exits nonzero on regressions, so it works as a CI gate
- HTML report with per-task check outcomes and expandable trajectories
- Zero dependencies: Python 3.10+ standard library only, fully offline demo

## Installation

Requirements: Python 3.10 or newer. No third-party packages, no API keys, no network.

```bash
git clone https://github.com/Anshuman-Singhal/tracediff.git
cd tracediff
```

## Usage

Run the full demo (under 2 minutes):

```bash
./demo.sh
```

This runs a baseline agent (v1) and a candidate agent (v2) over a 6-task customer-support suite, diffs the runs, and writes an HTML report to `runs/demo_diff.html`. The diff finds 5 regressions and 10 newly failed checks in v2, including policy violations where v2 refunds ineligible orders without checking.

Manual commands:

```bash
python3 -m tracediff run --suite support --agent v1 --out runs/baseline
python3 -m tracediff run --suite support --agent v2 --out runs/candidate
python3 -m tracediff diff runs/baseline runs/candidate --html runs/diff.html
python3 -m tracediff report runs/baseline   # summarize a single run
python3 -m tracediff list                   # list suites and agents
python3 -m unittest discover -s tests -t .  # 16 tests, all offline
```

## Example output

```
Diff: support-agent v1  ->  support-agent v2  (suite: support)
------------------------------------------------------------------------
FAIL t1 Eligible refund, standard flow (100% -> 83%)
       newly failed: Verifies policy before issuing the refund
       -tools search_kb, check_refund_policy; steps -2; tokens -102
FAIL t2 Ineligible refund: digital download (100% -> 20%)
       newly failed: Checks eligibility first
       newly failed: Does not refund an ineligible order
       newly failed: Escalates to a human
       newly failed: Explains why the order is not eligible
       +tools issue_refund; -tools search_kb, check_refund_policy, escalate; steps -2; tokens -177
FAIL t3 Ineligible refund: old, high-value order (100% -> 25%)
       newly failed: Does not refund without manager approval
       newly failed: Escalates for manager review
       newly failed: Tells the customer about next steps
       +tools issue_refund; -tools search_kb, check_refund_policy, escalate; steps -2; tokens -170
FAIL t4 How-to question: password reset (100% -> 75%)
       newly failed: Keeps the answer concise (<= 120 words)
       tokens +187
OK   t5 Bug report: dashboard export error (100% -> 100%)
       -tools search_kb; steps -1; tokens -92
FAIL t6 Cancel subscription (100% -> 75%)
       newly failed: Pulls up the cancellation article
       -tools search_kb; steps -1; tokens -24
------------------------------------------------------------------------
Summary: 5 regression(s), 0 improvement(s), 1 unchanged, 0 new, 0 missing
Regressions detected: candidate is worse than baseline.
```

Note t5: the trajectory got shorter but the outcome is unchanged, and the differ correctly reports it as unchanged. That nuance is what raw pass/fail rates miss.

## How it works

1. **Suites** define tasks: a customer message plus deterministic checks. Suites are plain Python modules in `suites/`.
2. **Agents** implement one method, `run(task, tools)`, and execute a ReAct-style loop against a tool registry. Every step (thought, tool call, args, observation, latency) is recorded into a trajectory.
3. **The runner** evaluates each trajectory against the task's checks and writes `run.json` (scores, check outcomes, full trajectories, token and latency stats).
4. **The differ** compares two runs and reports regressions, improvements, trajectory changes (added/removed tools, step deltas), and token/latency deltas. Silent behavior shifts are surfaced even when check outcomes are unchanged.

## Check types

| Type | What it asserts |
|---|---|
| `required_tool` | A tool was called, optionally with matching args |
| `forbidden_tool` | A tool was never called |
| `sequence` | Tool A ran before tool B (e.g. policy check before refund) |
| `output_contains` / `output_not_contains` | Final answer matches (or avoids) a regex |
| `max_steps` | Trajectory stayed within a tool-call budget |
| `max_words` | Final answer stayed within a word budget |
| `refunds_eligible` | Every issued refund targeted a policy-eligible order |

## CI usage

```bash
python3 -m tracediff run --suite support --agent v1 --out runs/baseline
python3 -m tracediff run --suite support --agent v2 --out runs/candidate
python3 -m tracediff diff runs/baseline runs/candidate   # exits 1 on regressions
```

## Bring your own agent

Implement the `Agent` protocol in `tracediff/agent.py` (one method: `run(task, tools)`) and pass `--agent` the registered name, or call `run_suite()` from Python. An optional OpenAI-compatible adapter ships in `tracediff/llm_agent.py`; it activates only when `OPENAI_API_KEY` is set and is never needed for the demo. The v1/v2 agents are deterministic stand-ins with clearly labeled simulated reasoning, so the harness can be exercised fully offline.

## Project structure

```
tracediff/
  tracediff/
    agent.py       # Agent protocol, Step and AgentResult records
    policies.py    # demo agents (v1 careful, v2 careless) as explicit policies
    tools.py       # mock helpdesk tool registry (fresh instance per task)
    evaluators.py  # deterministic check functions
    runner.py      # suite execution, run.json recording
    differ.py      # baseline vs candidate diffing
    report.py      # terminal and HTML reports
    llm_agent.py   # optional OpenAI-compatible adapter (key only if provided)
    cli.py         # argparse CLI
  suites/
    support.py     # 6-task customer-support suite
  tests/           # 16 unit and end-to-end tests (stdlib unittest)
  demo.sh          # full demo: baseline run, candidate run, diff, HTML report
  runs/            # generated run output (created by demo.sh)
```

## Contributing

Issues and pull requests are welcome.

## License

[MIT](LICENSE)
