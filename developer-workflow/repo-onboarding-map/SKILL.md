---
name: repo-onboarding-map
description: Produces the first-thirty-minutes map of a whole repository — how it is laid out, how to run and test it, which files carry the most change, and where the decisions were written down. Reads what the repository actually does rather than what its README claims. Use when the user needs to get oriented in an entire codebase they do not know — joining one, reviewing one they do not own, or asking how a project is structured and how to get it running. It is a survey, so it does not apply to a question about one part of a codebase — locating a single file, explaining one function, or asking how to carry out a specific change are each one lookup, and a whole-repository map is a disproportionate answer to them.
allowed-tools: Read Grep Glob Bash(git log:*) Bash(git shortlog:*) Bash(python3:*)
---

# Repo onboarding map

The question behind "what is this codebase" is almost never "describe every directory". It
is: where does execution start, how do I run it, which parts are alive, and what do I need
to know before I touch anything.

A generated tour that walks the directory tree answers none of those. This one is ordered
by what a newcomer needs first.

## Procedure

### 1. Get the mechanical map

`<skill-dir>` is the directory this SKILL.md was loaded from — the skill installs outside
your project, so its script is named by full path, never relatively.

```
python3 <skill-dir>/scripts/repo_map.py          # whole repo
python3 <skill-dir>/scripts/repo_map.py --top 25 # widen the hot-files list
```

The script detects the stack from its manifests, lists workspace packages, extracts the
declared run/test/build commands, finds entry points, ranks files by commit count, and
locates docs and agent-instruction files. It reports what it found, not what it expected
to find — a missing test command is reported as missing rather than guessed.

### 2. Read the instruction files first, if there are any

`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.cursorrules`. These are the highest-value
files in an unfamiliar repository and newcomers routinely miss them: they encode the
conventions that are not derivable from the code, and they are usually the only written
record of *why* the layout is what it is. Read them before forming any opinion about the
structure.

### 3. Follow the hot files, not the big ones

The commit ranking is the fastest route to where the work actually happens. A large file
that has not changed in a year is settled; a medium file with sixty commits is the one
you will be editing. Read the top five before anything else.

### 4. Verify the run and test commands rather than repeating them

The commands in `package.json` or the README are claims. Where it is safe and cheap, check
that the entry points they reference exist. **Do not run install, build, migration or
deploy commands** to find out — say which commands you verified structurally and which you
took on trust.

### 5. Name what you could not work out

An honest map has holes in it, and stating them is more useful than a smooth account that
quietly guesses. If you could not tell how configuration is loaded, or which of three
apps is the real entry point, that is the most useful sentence in the report — it is the
first question the newcomer should ask a human.

## Output

Keep it to one screen where possible:

1. **What this is** — one sentence, from the manifests and instruction files
2. **Layout** — the handful of directories that matter, not the whole tree
3. **Run it** — install, dev, test, build, with a note on which were verified
4. **Where the work happens** — the top churned files, with one line each
5. **Conventions to know** — from the instruction files, the ones that would trip a
   newcomer
6. **Open questions** — what you could not determine

## What this skill deliberately does not do

- **It does not write documentation into the repository.** It produces a map for a reader;
  committing an onboarding doc is a separate decision, and an unrequested `ONBOARDING.md`
  is noise in someone else's project.
- **It does not run install, build, migration or deploy commands.** Onboarding is exactly
  the moment when the blast radius of a stray command is least understood.
- **It does not describe every directory.** Completeness here is the enemy — a tour of
  forty folders is what the file tree already gives you for free.
- **It does not trust the README over the code.** Where they disagree, it reports both and
  says which is which.
- **It does not invent architecture.** If the layering is unclear, that goes in open
  questions rather than into a confident paragraph.

## When this is the wrong tool

- **The README's claims are what you care about.** Checking them against the code is
  verification, not orientation, and it wants a claim-by-claim pass rather than a map.
- **You are about to change something and want to know what depends on it.** That is a
  call-site question about one symbol, not a survey of the repository.
- **You want to know what is untested.** That is a coverage question.
