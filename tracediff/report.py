"""Terminal and HTML reports for run diffs."""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from .differ import DiffReport

_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def _pct(x: float) -> str:
    return f"{x:.0%}"


def print_terminal(report: DiffReport) -> None:
    print(f"\nDiff: {report.baseline_agent}  ->  {report.candidate_agent}  (suite: {report.suite})")
    print("-" * 72)
    for t in report.tasks:
        if t.status == "regression":
            sym, color = "FAIL", _RED
        elif t.status == "improvement":
            sym, color = "FIX ", _GREEN
        elif t.status == "new":
            sym, color = "NEW ", _YELLOW
        elif t.status == "missing":
            sym, color = "MISS", _YELLOW
        else:
            sym, color = "OK  ", _DIM
        print(
            f"{color}{sym}{_RESET} {t.task_id} {t.title} "
            f"({_pct(t.score_before)} -> {_pct(t.score_now)})"
        )
        for name in t.newly_failed:
            print(f"       {_RED}newly failed:{_RESET} {name}")
        for name in t.newly_passed:
            print(f"       {_GREEN}newly passed:{_RESET} {name}")
        traj_bits = []
        if t.added_tools:
            traj_bits.append(f"+tools {', '.join(t.added_tools)}")
        if t.removed_tools:
            traj_bits.append(f"-tools {', '.join(t.removed_tools)}")
        if t.step_delta:
            traj_bits.append(f"steps {t.step_delta:+d}")
        if t.token_delta:
            traj_bits.append(f"tokens {t.token_delta:+d}")
        if traj_bits:
            print(f"       {_DIM}{'; '.join(traj_bits)}{_RESET}")
    s = report.summary
    print("-" * 72)
    print(
        f"Summary: {s['regression']} regression(s), {s['improvement']} improvement(s), "
        f"{s['unchanged']} unchanged, {s['new']} new, {s['missing']} missing"
    )
    if report.has_regressions:
        print(f"{_RED}Regressions detected: candidate is worse than baseline.{_RESET}")
    else:
        print(f"{_GREEN}No regressions: candidate is safe to ship.{_RESET}")


_CSS = """
body { font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #1f2328; }
h1 { font-size: 1.6rem; } h2 { font-size: 1.2rem; margin-top: 2rem; border-bottom: 1px solid #d0d7de; padding-bottom: .3rem; }
.cards { display: flex; gap: .75rem; flex-wrap: wrap; margin: 1rem 0; }
.card { border: 1px solid #d0d7de; border-radius: 8px; padding: .6rem 1rem; min-width: 120px; }
.card .n { font-size: 1.5rem; font-weight: 700; }
table { border-collapse: collapse; width: 100%; font-size: .9rem; }
th, td { border: 1px solid #d0d7de; padding: .45rem .6rem; text-align: left; vertical-align: top; }
th { background: #f6f8fa; }
.pill { display: inline-block; padding: .1rem .55rem; border-radius: 999px; font-size: .75rem; font-weight: 600; color: #fff; }
.regression { background: #cf222e; } .improvement { background: #1a7f37; } .unchanged { background: #6e7781; }
.new { background: #9a6700; } .missing { background: #6e7781; }
.fail { color: #cf222e; font-weight: 600; } .pass { color: #1a7f37; }
details { margin: .4rem 0; } summary { cursor: pointer; color: #0969da; }
.step { background: #f6f8fa; border-radius: 6px; padding: .5rem .75rem; margin: .4rem 0; font-size: .85rem; }
.step .thought { font-style: italic; color: #57606a; }
code { background: #eef1f4; padding: .1rem .3rem; border-radius: 4px; font-size: .82rem; }
.muted { color: #57606a; font-size: .85rem; }
"""


def _task_rows(report: DiffReport) -> str:
    rows = []
    for t in report.tasks:
        failed = "".join(f"<div class='fail'>newly failed: {html.escape(n)}</div>" for n in t.newly_failed)
        passed = "".join(f"<div class='pass'>newly passed: {html.escape(n)}</div>" for n in t.newly_passed)
        traj = []
        if t.added_tools:
            traj.append(f"+tools: {', '.join(html.escape(x) for x in t.added_tools)}")
        if t.removed_tools:
            traj.append(f"-tools: {', '.join(html.escape(x) for x in t.removed_tools)}")
        if t.step_delta:
            traj.append(f"steps {t.step_delta:+d}")
        if t.token_delta:
            traj.append(f"tokens {t.token_delta:+d}")
        if t.latency_delta_ms:
            traj.append(f"latency {t.latency_delta_ms:+.1f}ms")
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(t.task_id)}</code><br>{html.escape(t.title)}</td>"
            f"<td><span class='pill {t.status}'>{t.status}</span></td>"
            f"<td>{_pct(t.score_before)} &rarr; {_pct(t.score_now)}</td>"
            f"<td>{failed}{passed}<div class='muted'>{'; '.join(traj)}</div></td>"
            "</tr>"
        )
    return "\n".join(rows)


def _trajectory_section(
    title: str, run: dict[str, Any] | None, agent_label: str
) -> str:
    if run is None:
        return ""
    parts = [f"<h2>Trajectories: {html.escape(agent_label)} ({html.escape(run.get('agent', ''))})</h2>"]
    for task_id, t in run.get("tasks", {}).items():
        checks = "".join(
            f"<div class='{'pass' if c['passed'] else 'fail'}'>"
            f"{'PASS' if c['passed'] else 'FAIL'}: {html.escape(c['name'])}"
            f"<span class='muted'> ({html.escape(c['detail'])})</span></div>"
            for c in t["checks"]
        )
        steps = "".join(
            "<div class='step'>"
            f"<div class='thought'>Thought: {html.escape(s['thought'])}</div>"
            + (
                f"<div>Tool: <code>{html.escape(s['tool'])}</code> "
                f"<code>{html.escape(str(s['args']))}</code></div>"
                f"<div>Observation: {html.escape(s['observation'])}</div>"
                if s["tool"]
                else "<div>Final answer step (no tool call).</div>"
            )
            + "</div>"
            for s in t["steps"]
        )
        parts.append(
            f"<details><summary><code>{html.escape(task_id)}</code> "
            f"{html.escape(t.get('title', ''))} (score {_pct(t.get('score', 1.0))})</summary>"
            f"<p><strong>Final answer:</strong> {html.escape(t.get('final_answer', ''))}</p>"
            f"<p><strong>Checks:</strong></p>{checks}"
            f"<p><strong>Trajectory:</strong></p>{steps}</details>"
        )
    return "\n".join(parts)


def write_html(
    report: DiffReport,
    baseline: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
    path: str | Path,
) -> Path:
    s = report.summary
    cards = "".join(
        f"<div class='card'><div class='n'>{s[k]}</div><div>{k}</div></div>"
        for k in ("regression", "improvement", "unchanged", "new", "missing")
    )
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>tracediff report: {html.escape(report.baseline_agent)} vs {html.escape(report.candidate_agent)}</title>
<style>{_CSS}</style></head>
<body>
<h1>tracediff report</h1>
<p class="muted">Baseline <code>{html.escape(report.baseline_agent)}</code> vs
candidate <code>{html.escape(report.candidate_agent)}</code> on suite
<code>{html.escape(report.suite)}</code>.</p>
<div class="cards">{cards}</div>
<h2>Per-task diff</h2>
<table><tr><th>Task</th><th>Status</th><th>Score</th><th>Changes</th></tr>
{_task_rows(report)}</table>
{_trajectory_section("baseline", baseline, "Baseline")}
{_trajectory_section("candidate", candidate, "Candidate")}
</body></html>"""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    return out
