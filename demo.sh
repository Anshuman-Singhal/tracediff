#!/usr/bin/env bash
# Demo: run the support suite against v1 (baseline) and v2 (candidate),
# diff the runs, and write an HTML report. Takes a few seconds.
set -euo pipefail
cd "$(dirname "$0")"

rm -rf runs/demo_baseline runs/demo_candidate
python3 -m tracediff run --suite support --agent v1 --out runs/demo_baseline
echo
python3 -m tracediff run --suite support --agent v2 --out runs/demo_candidate
echo
set +e
python3 -m tracediff diff runs/demo_baseline runs/demo_candidate --html runs/demo_diff.html
diff_exit=$?
set -e

echo
echo "HTML report: runs/demo_diff.html"
if [ "$diff_exit" -eq 1 ]; then
  echo "Exit code 1 is expected here: the candidate regressed, which is exactly what tracediff is built to catch."
fi
