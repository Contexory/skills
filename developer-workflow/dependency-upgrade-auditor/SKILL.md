---
name: dependency-upgrade-auditor
description: Works out what a dependency upgrade actually breaks for you, by extracting the specific APIs your code imports from a package and reading the release notes against that list rather than in general. Use when the user is upgrading a package, evaluating whether a version bump is safe, or asks why something broke after a dependency changed.
allowed-tools: Read Grep Glob WebFetch Bash(git log:*) Bash(python3:*)
---

# Dependency upgrade auditor

A major version's release notes describe everything that changed for everybody. Almost
none of it applies to you. The work is intersecting their breaking-change list with the
handful of APIs you actually call, and that intersection is usually small enough to check
line by line.

Reading a changelog top to bottom produces a summary of someone else's release. Reading it
against your own import list produces a decision.

## Procedure

### 1. Extract what you actually use

`<skill-dir>` is the directory this SKILL.md was loaded from — the skill installs outside
your project, so its script is named by full path, never relatively.

```
python3 <skill-dir>/scripts/dep_usage.py react-router     # one package
python3 <skill-dir>/scripts/dep_usage.py --all            # every direct dependency, summarised
```

The script reports the declared version range, every file importing the package, and the
**specific named imports, called members and subpath imports** in use. That last list is
the one that matters — it is what you check the changelog against.

### 2. Get the real changelog, not a summary of it

Prefer, in order: the package's `CHANGELOG.md` in its published tarball or repository, the
GitHub release notes for each intervening version, then a migration guide. Read every
version between the installed one and the target, not just the target — breaking changes
land in the majors you are skipping over.

If you cannot reach the notes, **say so and stop**. Guessing at a changelog produces
confident, invented migration steps, which is worse than no answer.

### 3. Intersect, and be specific about the misses

For each breaking change in the notes, decide: does it touch an API in the step-1 list?
Most will not. Report the ones that do with the call site, and state how many you
dismissed — the count is what tells the reader you read the whole list rather than
stopping at the first hit.

### 4. Check the quiet categories

The intersection catches renamed and removed APIs. Four kinds of break do not show up as
an API you import, and each needs a deliberate look:

- **peer dependency ranges** that no longer overlap with what you have installed
- **runtime floor** raised — a new minimum Node, Python or compiler version
- **default behaviour changes** under an unchanged signature, which the intersection
  cannot see because the name did not move
- **transitive** breakage, where the package you are bumping pulls a new major of
  something else

### 5. Rank the work

Output an ordered list: what must change before the upgrade compiles, what must change
before it behaves correctly, and what is merely deprecated and can wait. Those are three
different urgencies and collapsing them into one list is how upgrades stall.

## Output

1. **Versions** — from, to, and how many majors are being crossed
2. **Surface in use** — the APIs this repo imports, and how many call sites
3. **Breaking changes that hit you** — each with the call site and the fix
4. **Dismissed** — how many breaking changes did not apply, so the reader knows the list
   was read to the end
5. **Quiet risks** — peers, runtime floor, behaviour changes, transitives
6. **Order of work** — compile-blocking, behaviour-blocking, deferrable

## What this skill deliberately does not do

- **It does not invent a changelog.** If the release notes cannot be fetched, it says so
  and stops rather than reconstructing plausible migration steps from the version number.
- **It does not run the upgrade.** No installs, no lockfile edits, no `package.json`
  changes — the audit informs a decision that is the author's to make.
- **It does not report every breaking change in the release.** The ones that miss your
  code are noise, and the count is enough.
- **It does not assume semver was honoured.** A minor can break you; the intersection is
  run regardless of the bump's advertised size.
- **It does not audit transitive dependencies it was not asked about**, beyond naming the
  ones this bump drags along.

## When this is the wrong tool

- **Something is already failing and you have a trace.** Start from the trace — it names a
  frame, which is more than any changelog will. Come back here if it lands in vendored code.
- **The changed surface is your own code, not a dependency's.** That is a question about
  your own exports and who calls them.
- **You want the upgrade written up for a release.** Announcing a change and deciding
  whether to take it are different jobs.
