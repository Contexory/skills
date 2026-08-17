#!/usr/bin/env bash
# Syntax-check every skill script. Pack convention: the mechanical half of a
# skill is a script, not prose — and a script that does not parse is prose with
# extra steps.
#
# A separate file rather than an inline `run:` block so the workflow's every
# step is a single command that a test can read out of the workflow and execute
# verbatim. Two statements of "what CI runs" is how a green local check and a
# red CI run happen.
set -euo pipefail
shopt -s nullglob

found=0
for script in */*/scripts/*.py; do
  echo "python  $script"
  # `ast.parse` rather than `py_compile`, which writes the .pyc explicitly and
  # therefore ignores PYTHONDONTWRITEBYTECODE — it left a `__pycache__/` in all
  # nine skill directories, in a repository people are told to copy from. This
  # parses and writes nothing.
  python3 -c 'import ast,sys; ast.parse(open(sys.argv[1]).read(), sys.argv[1])' "$script"
  found=$((found + 1))
done
for script in */*/scripts/*.sh; do
  echo "bash    $script"
  bash -n "$script"
  found=$((found + 1))
done

# A glob that matches nothing is how this check silently stops checking anything
# the day the layout moves. Skills live at <pack>/<skill>/scripts/.
if [ "$found" -eq 0 ]; then
  echo "No skill scripts matched */*/scripts/* — has the layout changed?" >&2
  exit 1
fi
echo "$found script(s) parsed."
