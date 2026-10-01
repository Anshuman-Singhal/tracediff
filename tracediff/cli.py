"""Command-line interface for tracediff."""
from __future__ import annotations

import argparse
import sys

from .differ import diff_runs
from .policies import POLICIES, PolicyAgent
from .report import print_terminal, write_html
from .runner import list_suites, load_run, run_suite


def _resolve_agent(name: str):
    if name in POLICIES:
        return PolicyAgent(POLICIES[name])
    if name == "openai":
        from .llm_agent import OpenAIAgent

        return OpenAIAgent()
    raise SystemExit(
        f"Unknown agent '{name}'. Built-in agents: {', '.join(sorted(POLICIES))}, openai"
    )


def cmd_run(args: argparse.Namespace) -> int:
    agent = _resolve_agent(args.agent)
    run_suite(args.suite, agent, args.out, task_ids=args.tasks)
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    baseline = load_run(args.baseline)
    candidate = load_run(args.candidate)
    report = diff_runs(baseline, candidate)
    print_terminal(report)
    if args.html:
        out = write_html(report, baseline, candidate, args.html)
        print(f"HTML report written to {out}")
    return 1 if report.has_regressions else 0


def cmd_report(args: argparse.Namespace) -> int:
    run = load_run(args.run_dir)
    print(f"Run: agent={run['agent']} suite={run['suite']}")
    for task_id, t in run["tasks"].items():
        passed = sum(1 for c in t["checks"] if c["passed"])
        total = len(t["checks"])
        print(f"  {task_id}: {passed}/{total} checks passed (score {t['score']:.0%})")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    print("Suites:")
    for s in list_suites():
        print(f"  {s}")
    print("Agents:")
    for a in sorted(POLICIES):
        print(f"  {a} ({POLICIES[a].name})")
    print("  openai (requires OPENAI_API_KEY)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tracediff",
        description="Regression testing for AI agents: diff behavior across agent versions.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run a task suite against an agent.")
    p_run.add_argument("--suite", required=True, help="Suite name (see: tracediff list).")
    p_run.add_argument("--agent", required=True, help="Agent name (see: tracediff list).")
    p_run.add_argument("--out", required=True, help="Output directory for run.json.")
    p_run.add_argument("--tasks", nargs="*", default=None, help="Only run these task IDs.")
    p_run.set_defaults(func=cmd_run)

    p_diff = sub.add_parser("diff", help="Diff two runs. Exits 1 when regressions are found.")
    p_diff.add_argument("baseline", help="Directory containing the baseline run.json.")
    p_diff.add_argument("candidate", help="Directory containing the candidate run.json.")
    p_diff.add_argument("--html", default=None, help="Write an HTML report to this path.")
    p_diff.set_defaults(func=cmd_diff)

    p_report = sub.add_parser("report", help="Summarize a single run.")
    p_report.add_argument("run_dir", help="Directory containing run.json.")
    p_report.set_defaults(func=cmd_report)

    p_list = sub.add_parser("list", help="List available suites and agents.")
    p_list.set_defaults(func=cmd_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
