---
name: regression-risk-mapper
description: Maps what a change can reach — a change being considered as readily as one already made, since the question is usually asked before the edit exists. Finds the symbols involved, traces every call site and importer across the repository, and marks which of those call sites are exercised by a test and which are not. Use when the user asks what something might break, what depends on a symbol they are about to modify, rename or change the return type of, how far the blast radius of a refactor extends, or whether an edit is safe to make. Not for finding usages as an end in itself — with no change in prospect, that is a plain search and answering it with a risk analysis is more than was asked.
allowed-tools: Read Grep Glob Bash(git diff:*) Bash(python3:*)
---

# Regression risk mapper

The diff shows what you changed. It does not show who was relying on it. This skill
answers the second question, and it answers it with call sites rather than with intuition.

The failure it prevents is specific and common: a signature or behaviour is changed with
its two obvious callers updated, and the third caller — in another package, reached
through a re-export, written before anyone currently on the team joined — is discovered in
production.

## Procedure

### 1. Map the radius

`<skill-dir>` is the directory this SKILL.md was loaded from — the skill installs outside
your project, so its script is named by full path, never relatively.

```
python3 <skill-dir>/scripts/blast_radius.py             # working tree vs merge-base with main
python3 <skill-dir>/scripts/blast_radius.py origin/main # or an explicit base
```

For every symbol the diff modifies, the script finds every file referencing it, marks each
reference `direct` or `re-export`, and marks whether the referencing file has a
corresponding test file. It prints a per-symbol radius, ordered by number of call sites.

**Read the caveat it prints.** The search is textual. It cannot see dynamic dispatch,
string-keyed lookup, reflection, or a caller in another repository, and it says so — those
are the paths that stay invisible and they are exactly where the expensive surprises live.

### 2. Separate signature changes from behaviour changes

They fail differently and need different checks:

- **Signature change** — the compiler or type checker finds the callers for you. Run the
  type check and trust it. The risk here is the untyped edge: JSON boundaries, dynamic
  imports, plugin entry points, anything crossing a process.
- **Behaviour change** — nothing finds the callers for you. Same signature, different
  result: a changed default, a different sort order, a null where an empty array used to
  be, a function that now throws. **This is where the radius map earns its keep**, and
  every call site has to be read.

Say which of the two you are dealing with before going further. If it is both, treat it as
behaviour.

### 3. Read the uncovered call sites first

The script marks call sites in files with no paired test. Those are the ones where a
regression ships silently. Read each and ask the narrow question: does this caller depend
on the thing that changed, or does it merely use the same symbol?

### 4. Follow re-exports one hop further

A barrel file that re-exports a changed symbol turns the radius into everything importing
the barrel. The script marks these; expand them once, and say plainly if the result is too
large to enumerate rather than pretending to have checked it.

### 5. Name the specific regression, or say there is none

The output is not "this is risky". It is "`renderInvoice` in `billing/pdf.ts` assumes this
returns a sorted array, and it no longer does" — or an explicit "no caller depends on the
changed behaviour", which is a real and useful answer.

## Output

1. **Change type** — signature, behaviour, or both
2. **Radius** — symbols changed, call sites reached, how many are untested
3. **Specific risks** — file, line, and the assumption that no longer holds
4. **Invisible edges** — dynamic dispatch, cross-repo consumers, serialized boundaries the
   text search cannot reach
5. **Verdict** — what to test before merging, or "nothing depends on this"

## What this skill deliberately does not do

- **It does not claim the map is complete.** A textual search has known blind spots, and
  the report names them every time rather than in a footnote. A blast-radius tool that
  implies completeness is more dangerous than none.
- **It does not fix the callers.** It reports; changing them is a separate decision with
  its own review.
- **It does not flag every reference as a risk.** A file that imports a changed symbol but
  does not touch the changed behaviour is not a finding, and reporting it as one buries
  the two that matter.
- **It does not run the test suite** to find out. That is slower than reading, and a green
  suite would not prove the uncovered call sites are safe — it would prove they are
  uncovered.
- **It does not extend past one re-export hop** without saying so.

## When this is the wrong tool

- **The failure has already happened and you have a trace.** Start there — a real frame
  beats a predicted radius every time.
- **You want the change reviewed on its own terms, inside the diff.** That is a review;
  this skill's whole job is to leave the diff.
- **The change is a dependency version rather than your own code.** The changed surface is
  someone else's, and reading their changelog against your call sites is a different
  procedure.
