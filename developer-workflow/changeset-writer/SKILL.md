---
name: changeset-writer
description: Writes the release note for a change using the repository's own convention, and picks the version bump from what the change did to the public surface rather than from how big the diff looks. Detects Changesets, Conventional Commits or a hand-maintained changelog and follows whichever is already in use. Use when the user needs a changeset, release note, changelog entry or version bump decision for work they just finished.
allowed-tools: Read Grep Glob Bash(git diff:*) Bash(git log:*) Bash(python3:*)
---

# Changeset writer

Two things go wrong with release notes, and both are mechanical enough to fix.

The note describes the diff instead of the consequence — "refactored the parser" tells a
consumer nothing about whether to upgrade. And the bump is chosen by feel: a large diff
gets a minor, a small one gets a patch, when the only question that matters is what
happened to the surface other people depend on.

## Procedure

### 1. Read the change's effect on the public surface

`<skill-dir>` is the directory this SKILL.md was loaded from — the skill installs outside
your project, so its script is named by full path, never relatively.

```
python3 <skill-dir>/scripts/change_surface.py             # working tree vs merge-base with main
python3 <skill-dir>/scripts/change_surface.py origin/main # explicit base
```

The script reports which packages the diff touches, whether each is published or private,
the exported symbols **added, removed and signature-changed** per package, and the
repository's existing release convention with an example of a recent entry.

### 2. Pick the bump from the surface, not the diff size

- **major** — an export was removed, renamed, or had its signature narrowed; a default
  changed in a way existing callers would notice; a runtime floor was raised
- **minor** — an export was added, and nothing existing changed
- **patch** — no change to the public surface at all

A private package usually needs no changeset. Say so rather than writing an empty one.

**A large internal refactor with an unchanged surface is a patch.** This is the case people
get wrong most often, and getting it right is most of this skill's value.

### 3. Write for the person deciding whether to upgrade

They want to know: what can I now do that I could not, what will break, and what must I
change. Nothing else belongs in the entry. In particular, leave out the internal path — no
file names, no "moved X into Y", no ticket references unless the convention already
includes them.

If the change is user-invisible, the honest entry is a one-liner. Padding it is worse than
brevity.

### 4. Match the existing voice exactly

The script prints recent entries. Match their person, tense, and whether they begin with a
verb. A correct entry in the wrong voice still reads as an outsider's, and consistency
here is most of what a changelog is for.

### 5. Flag a breaking change loudly, and write the migration inline

If step 2 landed on major, the entry needs the before and the after in code, not a
description of them. A consumer reading a breaking change wants to see the two lines side
by side.

## Output

The entry itself, in the repository's format and ready to paste or write to the right
path — plus, separately:

1. **Bump and why** — which surface change drove it
2. **Packages affected** — and which were skipped as private
3. **Anything you could not classify** — a behaviour change that the surface diff cannot
   see is worth naming explicitly

## What this skill deliberately does not do

- **It does not invent a convention.** If the repository has no changeset or changelog
  system, it says so and asks rather than introducing one — adding `.changeset/` to a repo
  that does not use Changesets is a real and annoying mess to undo.
- **It does not bump versions or edit `package.json`.** Version numbers are the release
  tool's job.
- **It does not describe the implementation.** File names and refactor narration are the
  most common failure in generated release notes.
- **It does not write an entry for a private package** without saying it is probably
  unnecessary.
- **It does not upgrade a patch to a minor to make the change sound more significant.**
- **It does not tag, push, or publish.**

## When this is the wrong tool

- **You want the change checked, not described.** This assumes the change is settled and
  only its announcement is open. Review it first if that is not true.
- **You want to know what the change might break.** That is a blast-radius question and it
  is answered by call sites, not by release notes.
- **The change is a dependency bump.** Its consequences come from that dependency's own
  changelog read against your call sites, not from your diff.
