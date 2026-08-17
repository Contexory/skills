#!/usr/bin/env bash
# Measure a command's failure rate by running it repeatedly.
#
#   bash rerun.sh "<command>" [runs] [--stop-after N]
#
# Prints a pass/fail strip, the observed rate, and a Wilson score interval — the
# interval matters because 3/10 and 30/100 are the same percentage and very
# different evidence. Exits 0 when the command never failed, 1 when it failed at
# least once, and 2 on bad usage.
#
# Deliberately dumb about what it runs: it never inspects, retries or repairs the
# command, and it captures each run's output so a failing run can be read rather
# than re-guessed.

set -uo pipefail

CMD="${1:-}"
RUNS="${2:-20}"
STOP_AFTER=0

if [ "${3:-}" = "--stop-after" ]; then
  STOP_AFTER="${4:-0}"
fi

if [ -z "$CMD" ]; then
  echo "usage: rerun.sh \"<command>\" [runs] [--stop-after N]" >&2
  exit 2
fi
# Digits-only, then non-zero. The digit test alone accepts `0`, which the message
# already calls invalid: zero runs skips the loop and then divides by `runs` in
# the Wilson block, so the script died on a ZeroDivisionError *and still exited
# 0* — a caller reads that as a successful measurement with no interval.
case "$RUNS" in
  ''|*[!0-9]*) echo "runs must be a positive integer" >&2; exit 2 ;;
esac
if [ "$RUNS" -lt 1 ]; then
  echo "runs must be a positive integer" >&2; exit 2
fi
# Same guard for --stop-after: it is compared with `-gt` on every iteration, so a
# non-numeric value prints a bash error per run while the measurement continues.
case "$STOP_AFTER" in
  ''|*[!0-9]*) echo "--stop-after takes a non-negative integer" >&2; exit 2 ;;
esac

LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/rerun.XXXXXX")"
trap 'echo; echo "run logs: $LOG_DIR"' EXIT

echo "command: $CMD"
echo "runs:    $RUNS"
echo

failures=0
strip=""
first_failure=""

for i in $(seq 1 "$RUNS"); do
  log="$LOG_DIR/run-$i.log"
  if bash -c "$CMD" >"$log" 2>&1; then
    strip="${strip}."
  else
    strip="${strip}X"
    failures=$((failures + 1))
    [ -z "$first_failure" ] && first_failure="$log"
  fi
  # Redraw in place only for a human at a terminal. Piped — which is how an agent
  # runs this — `\r` is not a cursor move, so every iteration lands as another
  # copy of the strip and a 40-run measurement becomes 40 lines of near-identical
  # noise in the reader's context.
  if [ -t 1 ]; then
    printf "\r  [%-${RUNS}s] %d/%d  failures: %d" "$strip" "$i" "$RUNS" "$failures"
  fi
  if [ "$STOP_AFTER" -gt 0 ] && [ "$failures" -ge "$STOP_AFTER" ]; then
    echo
    echo "  stopping early: reached $STOP_AFTER failure(s)"
    RUNS="$i"
    break
  fi
done

echo
echo "  runs: [$strip]   . = pass   X = fail"
echo

# Wilson score interval at 95%. Preferred to the normal approximation because the
# rates that matter here are near zero, where the normal interval goes negative
# and stops meaning anything.
python3 - "$failures" "$RUNS" <<'PY'
import math, sys

failures, runs = int(sys.argv[1]), int(sys.argv[2])
p = failures / runs if runs else 0.0
z = 1.96
denom = 1 + z * z / runs
centre = (p + z * z / (2 * runs)) / denom
margin = (z * math.sqrt(p * (1 - p) / runs + z * z / (4 * runs * runs))) / denom
low, high = max(0.0, centre - margin), min(1.0, centre + margin)

print(f"observed failure rate: {failures}/{runs} = {p * 100:.1f}%")
print(f"95% interval:          {low * 100:.1f}% – {high * 100:.1f}%")
if failures == 0:
    print(
        f"\nNot reproduced in {runs} runs. The true rate could still be as high as "
        f"{high * 100:.1f}% — report this as 'not reproduced', not as 'not flaky'."
    )
elif failures == runs:
    print(
        "\nFailed every run. This is a broken test, not a flaky one — diagnose it from "
        "the failure itself rather than measuring a rate that is already 100%."
    )
else:
    print(
        "\nReproduced. Next: run the test alone many times, then inside its file, then "
        "inside the whole suite. Only-fails-in-the-larger-set means ordering or shared "
        "state; fails-alone means timing or environment."
    )
PY

if [ -n "$first_failure" ]; then
  echo
  echo "first failing run: $first_failure"
  echo "── tail ──"
  tail -n 25 "$first_failure"
fi

[ "$failures" -eq 0 ] && exit 0 || exit 1
