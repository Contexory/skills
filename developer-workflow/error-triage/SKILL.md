---
name: error-triage
description: Locates the cause of a runtime failure inside this repository. Maps stack frames to real source files, separates first-party code from vendored frames, and surfaces the recent changes to the line that owns the failure. A pasted stack trace is the fastest input but not a requirement — it works from a CI or crash log, or from a failure the user only describes, in which case its first step is establishing what to capture. Use when something has already failed at runtime and the user wants to know why — a pasted exception, a job log, or a fault that appears in one environment and not another. Not for a failure the user describes as intermittent, where the rate has to be measured before anything can be diagnosed.
allowed-tools: Read Grep Glob Bash(git log:*) Bash(git blame:*) Bash(python3:*)
---

# Error triage

A stack trace names the frame where the process gave up, which is rarely the frame that
caused the failure. This skill finds the second one.

## Procedure

Work in order. Do not skip to step 4.

### 1. Map the trace to real files

Run the mapper on the trace. It accepts a file path or `-` for stdin, and it works on
Node, Python, Go and Java formats:

`<skill-dir>` is the directory this SKILL.md was loaded from — the skill installs outside
your project, so its script is named by full path, never relatively.

```
python3 <skill-dir>/scripts/trace_map.py -            # paste the trace on stdin
python3 <skill-dir>/scripts/trace_map.py /tmp/ci.log  # or read it from a file
```

It prints every frame in order, marks each as `project` or `vendor`, drops frames whose
file does not exist on disk, and labels the first surviving project frame `OWNING`. It
then runs `git blame` on that line and `git log` on that file.

**If the mapper resolves no project frames at all**, say so and stop the mechanical part —
the trace is from a different build of this code, or from a dependency's internals. Ask
for the commit the trace came from rather than guessing at frames that do not exist.

### 2. Read the owning frame, and the two frames either side of it

Read the actual source. The trace tells you a line number; it does not tell you what the
line assumed. What you are looking for is the assumption that no longer holds — a value
that can now be null, a shape that changed, an order that is no longer guaranteed.

### 3. Check whether the owning line is new

The mapper already printed `git blame` for the line and the last three commits touching
the file. A failure in a line that changed this week has a different explanation from one
that has been stable for two years and only started failing now. If the line is old, the
thing that changed is upstream of it — its **input** changed, not its logic. Follow the
input.

### 4. Look for the same failure elsewhere before proposing anything

Grep the repository for the error's distinctive text and for the symbol in the owning
frame. Three things are worth finding:

- an existing test that covers this path, which tells you what behaviour was intended
- an existing `catch` or guard for this exact case somewhere else, which tells you the
  team already knows about it and has a house pattern for it
- a second call site with the same shape, which tells you the fix belongs one level up

### 5. Reproduce before you propose

State the smallest command that reproduces it, and run it. If you cannot reproduce it,
say that plainly and give the two or three candidate causes ranked, with what would
distinguish them. **A confident fix for an unreproduced error is the failure mode this
skill exists to prevent.**

## Output

Report in this order, and keep it short:

1. **Owning frame** — `path:line`, and the one-sentence reason it is the owning frame
   rather than the top frame
2. **What broke** — the assumption that stopped holding
3. **When it started** — from blame and log, or "unchanged for N months, so the input
   changed"
4. **Reproduction** — the command, and whether it actually reproduced
5. **Fix** — only if step 5 succeeded. Otherwise: ranked candidates and the distinguishing
   test

## What this skill deliberately does not do

The precision floor matters more than coverage here. A triage tool that confidently names
the wrong line is worse than no tool, because it sends the reader somewhere specific.

- **It does not diagnose from the top frame alone.** If every project frame is filtered
  out, it reports that instead of falling back to the vendor frame.
- **It does not propose edits inside vendored code.** `node_modules`, `site-packages`,
  `vendor/` and the standard library are read-only context. A fix there is a version
  constraint or a call-site change, never an edit.
- **It does not rewrite the error handling it passes through.** Adding a `try/catch` to
  make a symptom disappear is out of scope, and is usually the wrong fix.
- **It does not guess at line numbers when the trace is minified** and no source map
  resolves. It says the trace is unusable and asks for one from a non-minified build.
- **It does not touch the failing code before reproducing it.**

## When this is the wrong tool

- **The failure is a test that passes on re-run.** That is intermittency, and reasoning
  from the source is actively misleading — measure the rate before diagnosing anything.
- **The failure appeared right after a dependency bump.** Read that dependency's changelog
  against the APIs you actually import first; a changed default explains a whole class of
  new failures faster than a trace will.
- **There is no error yet and you want to know what a diff might break.** That is a
  blast-radius question. Triage firing on it would invent a failure to explain.
