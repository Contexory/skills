/**
 * Pack lint — the gate every skill in this repository passes on every push and
 * pull request. See `.github/workflows/lint.yml`.
 *
 * Zero dependencies, on purpose. This repository ships skills, not an
 * application: a lockfile, an install step and a dependency surface would all
 * be things a reader has to audit before trusting the thing that validates the
 * skills. Everything here is `node:` builtins.
 *
 * ## The `allowed-tools` field
 *
 * The field is whitespace-separated, but a token's *scope* may itself contain
 * spaces — `Bash(pnpm test:*)` is real Claude Code syntax. So a plain
 * `split(/\s+/)` is wrong: it tears that token into `Bash(pnpm` and `test:*)`,
 * which are then each reported as invalid, failing a skill that was correct.
 *
 * That bug has been written more than once, in more than one reader of the same
 * field upstream, every time by someone re-implementing the split locally
 * because it looked like one line.
 * `parseAllowedTools` below is transcribed from the upstream Contexory
 * implementation — Contexory's own `skill-spec` module, which is not public —
 * rather than
 * re-derived, for the same reason `ALLOWED_TOOL_RE` and `DESCRIPTION_MAX` are:
 * this file is a *second statement* of rules the product also states, and a
 * second statement that was reasoned out independently is a second statement
 * that will disagree. Upstream binds the two together with a test that runs
 * both over the same corpus.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

// ── Vendored from Contexory's skill-spec module (not public) ──────────────

/**
 * A well-formed token (an identifier plus an optional `(...)` scope that may
 * contain spaces) or, failing that, any run of non-whitespace. The second
 * alternative is what keeps `Bash(git:*` and a stray `)` visible to validation;
 * the first is why the space inside a closed scope does not end the token.
 *
 * `[^\s()]+` rather than `\S+` in the first alternative so the scope cannot
 * start mid-token, and `[^)]*` rather than `.*` so two adjacent scoped tokens
 * are not merged across the gap between them.
 */
const ALLOWED_TOOL_TOKEN_RE = /[^\s()]+\([^)]*\)|\S+/g;

/** The shape a single token must have once the field is tokenized correctly. */
const ALLOWED_TOOL_RE = /^[A-Z][A-Za-z0-9]*(?:\([^)]+\))?$/;

/** A scope carrying whitespace — the token shape the naive split destroys. */
const MULTIWORD_SCOPE_RE = /^[A-Z][A-Za-z0-9]*\([^)]*\s[^)]*\)$/;

const SKILL_NAME_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const SKILL_NAME_MAX = 64;
/**
 * Names the product refuses on import, from the same non-public module.
 *
 * Transcribed alongside the regex and the length, because half a transcription
 * is the drift this file's header argues against: without it a contributor adds
 * `claude/`, the pack lint passes, and the product rejects the skill on import
 * — a failure that appears only after the pull request is merged.
 */
const RESERVED_NAMES = ["anthropic", "claude"];
const DESCRIPTION_MAX = 1024;
const TRIGGER_PHRASES = ["use this skill", "when the user", "for tasks involving", "use when"];

/** Split an `allowed-tools` value into its tokens. */
export function parseAllowedTools(raw) {
  return raw.match(ALLOWED_TOOL_TOKEN_RE) ?? [];
}

/**
 * Read `allowed-tools` out of parsed frontmatter, whatever shape it arrived in.
 * **This is the entry point for a reader of a document**; `parseAllowedTools` is
 * for a value already known to be a string.
 *
 * The field has two shapes in the wild. The scalar form
 * (`allowed-tools: Read Bash(git:*)`) is what the reference page teaches; the
 * sequence form (`allowed-tools: [Read, Bash(git:*)]`) is what YAML habits
 * suggest, and it is what Contexory's own sign-in screen renders as an example.
 * Readers that gated on `typeof value === "string"` reported the sequence form
 * as *no tools at all* — the same failure mode as the whitespace split, wearing
 * a different hat: the file keeps its tools and every derived surface disagrees,
 * with no error raised.
 *
 * A non-string scalar entry is stringified rather than dropped, for the same
 * reason the tokenizer returns malformed input: validation reports on whatever
 * comes back, so swallowing garbage here turns an error into a silent pass.
 * Shapes carrying no readable token yield nothing.
 */
export function allowedToolsFrom(value) {
  if (typeof value === "string") return parseAllowedTools(value);
  if (Array.isArray(value)) {
    return value.flatMap((entry) => {
      if (typeof entry === "string") return parseAllowedTools(entry);
      if (typeof entry === "number" || typeof entry === "boolean") return [String(entry)];
      return [];
    });
  }
  return [];
}

// ── Frontmatter ───────────────────────────────────────────────────────────

const FRONTMATTER_RE = /^---\s*\n([\s\S]*?)\n---\s*(?:\n|$)/;
const KEY_LINE_RE = /^([A-Za-z][A-Za-z0-9_-]*):(?:[ \t]+(.*))?$/;

/**
 * Strip a trailing `# comment` from an unquoted plain scalar.
 *
 * YAML starts a comment at a `#` preceded by whitespace, so
 * `description: text # note` is the value `text`. Keeping the comment was a
 * *silent wrong answer* rather than a red build: the comment text counted
 * toward the 1024-character limit and toward the trigger-phrase check, so a
 * description could pass or fail on words its author had already marked as an
 * aside. Quoted scalars are left alone — a `#` inside quotes is literal.
 */
function stripTrailingComment(value) {
  const quote = value[0];
  if (quote === '"' || quote === "'") {
    // Find the closing quote, honouring `\"` in double quotes and `''` in
    // single. Returning early on *any* quoted value was right for `"a # b"`,
    // where the hash is literal, and wrong for `"a" # b`, where it is a comment
    // — so a quoted description carried its own aside into the 1024-character
    // limit, which is the silent wrong answer this function exists to stop.
    let i = 1;
    while (i < value.length) {
      if (quote === '"' && value[i] === "\\") { i += 2; continue; }
      if (value[i] === quote) {
        if (quote === "'" && value[i + 1] === "'") { i += 2; continue; }
        break;
      }
      i++;
    }
    if (i >= value.length) return value; // unterminated; reported elsewhere
    const rest = value.slice(i + 1);
    if (rest.trim() === "") return value.slice(0, i + 1);
    // YAML needs whitespace before a `#` for it to open a comment.
    if (/^\s+#/.test(rest)) return value.slice(0, i + 1);
    return value;
  }
  const at = value.search(/\s#/);
  return at === -1 ? value : value.slice(0, at).trimEnd();
}

/** `|`, `>`, and their chomping variants. Nothing else — see `readBlockScalar`. */
const BLOCK_HEADER_RE = /^([|>])([-+]?)$/;

/**
 * Read a block scalar's body, folding or preserving it as YAML would.
 *
 * Supported because `description: >-` over two lines is simply how anyone
 * writes a description longer than one line, and rejecting it would red-build
 * the first outside contributor over a shape the product accepts.
 *
 * Everything it does not implement is refused by name rather than approximated:
 * an explicit indentation indicator (`>2`), and a more-indented line inside a
 * *folded* block, which YAML keeps literal and this does not fold correctly.
 * Guessing at either would be the mis-parse the strict reader exists to avoid.
 */
function readBlockScalar(lines, start, style, chomp, key, headerLine) {
  const body = [];
  let i = start;
  let indent = null;

  while (i < lines.length) {
    const line = lines[i];
    if (line.trim() === "") { body.push(""); i++; continue; }
    const leading = line.slice(0, line.length - line.trimStart().length);
    if (leading.includes("\t")) {
      // js-yaml: "tab characters must not be used in indentation". Counting a
      // tab as one indent character certified a file that no YAML reader can
      // load — the drift the vendoring exists to prevent, arriving from a
      // contributor's editor rather than from anyone's judgement.
      return {
        error: `Frontmatter line ${i + 1} indents \`${key}:\`'s block with a tab. YAML forbids tabs in indentation; use spaces.`,
      };
    }
    const lead = leading.length;
    if (lead === 0) break;
    if (indent === null) indent = lead;
    else if (lead < indent) break;
    else if (lead > indent && style === ">") {
      return {
        error: `Frontmatter line ${i + 1} is indented further than the rest of \`${key}:\`'s folded block. Use \`|\` if the extra indentation is meant literally.`,
      };
    }
    body.push(line.slice(indent));
    i++;
  }

  if (indent === null) {
    return { error: `Frontmatter line ${headerLine} opens a block scalar for \`${key}:\` with no content under it.` };
  }

  // Counted, not just discarded: trailing blank lines are the *only* thing `+`
  // means, so popping them before the chomp branch made keep and clip
  // identical — and the corpus fixture for "folded, kept" had no trailing
  // blanks, so it was structurally incapable of noticing. That is the
  // `Bash(git:*)` trap, reproduced inside the corpus written to prevent it.
  let trailingBlanks = 0;
  while (body.length > 0 && body[body.length - 1] === "") {
    body.pop();
    trailingBlanks++;
  }

  let text;
  if (style === "|") {
    text = body.join("\n");
  } else {
    // Fold: consecutive non-empty lines join with a space, a blank line becomes
    // a newline.
    const paragraphs = [];
    let current = [];
    for (const line of body) {
      if (line === "") { paragraphs.push(current.join(" ")); current = []; }
      else current.push(line);
    }
    paragraphs.push(current.join(" "));
    text = paragraphs.join("\n");
  }

  if (chomp === "-") return { value: text, next: i }; // strip
  if (chomp === "+") return { value: text + "\n".repeat(1 + trailingBlanks), next: i }; // keep
  return { value: `${text}\n`, next: i }; // clip
}

/**
 * Read a SKILL.md's frontmatter as a flat map of scalars.
 *
 * Deliberately strict rather than lenient. A skill's frontmatter in this pack
 * is `name`, `description` and `allowed-tools` — three unindented scalars — and
 * a parser that silently skipped the YAML shapes it does not implement (nested
 * maps, lists, block scalars) would report a skill as clean while having read
 * only part of it. Anything it cannot account for is a lint failure that names
 * the line, so the fix is obvious and nothing passes by omission.
 */
export function parseFrontmatter(raw) {
  const match = raw.match(FRONTMATTER_RE);
  if (!match) {
    return {
      ok: false,
      problem: {
        code: "frontmatter-missing",
        message: "SKILL.md has no `---` frontmatter block.",
      },
    };
  }

  const frontmatter = {};
  // Group 1 always participates when the regex matched at all, so no fallback.
  const lines = match[1].split("\n");
  // A text ending in a newline splits to a trailing "" that is not a line. It
  // only appears when blank lines precede the closing `---`, and counting it
  // gave block scalars one trailing newline too many under `+` chomping.
  if (match[1].endsWith("\n")) lines.pop();
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    const lineNo = index + 1;
    if (line.trim() === "" || line.trimStart().startsWith("#")) { index++; continue; }

    const keyed = line.match(KEY_LINE_RE);
    if (!keyed) {
      return {
        ok: false,
        problem: {
          code: "frontmatter-unparsed",
          message:
            `Frontmatter line ${lineNo} is not a plain \`key: value\` scalar: ${JSON.stringify(line)}. ` +
            "Pack frontmatter is a flat map — no nesting, lists or block scalars.",
        },
      };
    }

    const key = keyed[1];
    index++;
    const rawValue = stripTrailingComment((keyed[2] ?? "").trim());

    const blockHeader = rawValue.match(BLOCK_HEADER_RE);
    if (blockHeader) {
      const read = readBlockScalar(lines, index, blockHeader[1], blockHeader[2], key, lineNo);
      if (read.error) {
        return { ok: false, problem: { code: "frontmatter-unparsed", message: read.error } };
      }
      if (key in frontmatter) {
        return {
          ok: false,
          problem: {
            code: "frontmatter-duplicate-key",
            message: `Frontmatter declares \`${key}\` more than once (line ${lineNo}).`,
          },
        };
      }
      frontmatter[key] = read.value;
      index = read.next;
      continue;
    }

    // The flow-sequence form, `[Read, Bash(git:*)]`. Parsed into a real array
    // rather than left as a string, so `allowedToolsFrom` sees the shape the
    // product sees. Commas separate entries here exactly as they do in YAML,
    // which means a comma inside a scope splits the token in both readers —
    // agreeing with the product matters more than being cleverer than it.
    if (rawValue.startsWith("[")) {
      if (!rawValue.endsWith("]")) {
        return {
          ok: false,
          problem: {
            code: "frontmatter-unparsed",
            message: `Frontmatter line ${lineNo} opens a \`[\` sequence that does not close on the same line.`,
          },
        };
      }
      const inner = rawValue.slice(1, -1);
      if (/[[\]{}]/.test(inner)) {
        return {
          ok: false,
          problem: {
            code: "frontmatter-unparsed",
            message: `Frontmatter line ${lineNo} nests a sequence or mapping. Pack frontmatter is flat.`,
          },
        };
      }
      const entries = inner.trim() === "" ? [] : inner.split(",").map((part) => unquote(part.trim()));
      if (entries.some((entry) => entry === "")) {
        return {
          ok: false,
          problem: {
            code: "frontmatter-unparsed",
            message: `Frontmatter line ${lineNo} has an empty entry in its \`[...]\` sequence.`,
          },
        };
      }
      if (key in frontmatter) {
        return {
          ok: false,
          problem: {
            code: "frontmatter-duplicate-key",
            message: `Frontmatter declares \`${key}\` more than once (line ${lineNo}).`,
          },
        };
      }
      frontmatter[key] = entries;
      continue;
    }

    const value = unquote(rawValue);
    if (/^[|>]/.test(value)) {
      // `|` and `>` with their chomping indicators are handled above; anything
      // else starting that way is a form this reader does not implement —
      // an explicit indentation indicator, most likely.
      return {
        ok: false,
        problem: {
          code: "frontmatter-unparsed",
          message: `Frontmatter line ${lineNo} opens a block scalar this reader does not implement (${JSON.stringify(value)}). Use \`|\`, \`>\`, \`|-\` or \`>-\`.`,
        },
      };
    }
    if (key in frontmatter) {
      return {
        ok: false,
        problem: {
          code: "frontmatter-duplicate-key",
          message: `Frontmatter declares \`${key}\` more than once (line ${lineNo}).`,
        },
      };
    }
    frontmatter[key] = value;
  }

  return { ok: true, frontmatter, body: raw.slice(match[0].length) };
}

/** Strip a wrapping pair of quotes, honouring YAML's doubled single quote. */
function unquote(value) {
  if (value.length >= 2 && value.startsWith('"') && value.endsWith('"')) {
    return value.slice(1, -1);
  }
  if (value.length >= 2 && value.startsWith("'") && value.endsWith("'")) {
    return value.slice(1, -1).replaceAll("''", "'");
  }
  return value;
}

// ── The rules ─────────────────────────────────────────────────────────────

/**
 * Lint one skill from its already-read contents.
 *
 * Pure: `files` is the list of POSIX-relative paths inside the skill directory.
 * Keeping the filesystem out of here is what lets every rule be tested without
 * a fixture tree on disk.
 */
export function lintSkill({ dir, skillMd, files }) {
  const problems = [];
  const add = (code, message) => problems.push({ dir, code, message });

  const parsed = parseFrontmatter(skillMd);
  if (!parsed.ok) {
    // Return rather than continue: every downstream rule reads the frontmatter,
    // so carrying on would bury one real cause under six consequences.
    add(parsed.problem.code, parsed.problem.message);
    return problems;
  }
  const fm = parsed.frontmatter;

  // ── name ──
  const name = fm.name ?? "";
  if (!name) {
    add("name-missing", "Frontmatter has no `name`.");
  } else if (RESERVED_NAMES.includes(name.toLowerCase())) {
    add("name-reserved", `\`name: ${name}\` is reserved. Choose a more specific name.`);
  } else if (!SKILL_NAME_RE.test(name) || name.length > SKILL_NAME_MAX) {
    add(
      "name-format",
      `\`name: ${name}\` must be 1–${SKILL_NAME_MAX} characters of lowercase letters, digits and single hyphens.`,
    );
  } else if (name !== dir) {
    // The directory name is the install path, so a mismatch means the skill
    // installs under a name its own frontmatter does not use.
    add("name-directory-mismatch", `\`name: ${name}\` does not match its directory \`${dir}/\`.`);
  }

  // ── description ──
  const description = fm.description ?? "";
  if (!description) {
    add("description-missing", "Frontmatter has no `description` — it is how an agent decides to fire.");
  } else {
    if (description.length > DESCRIPTION_MAX) {
      add(
        "description-too-long",
        `Description is ${description.length} characters — the limit is ${DESCRIPTION_MAX}.`,
      );
    }
    const lower = description.toLowerCase();
    if (!TRIGGER_PHRASES.some((phrase) => lower.includes(phrase))) {
      add(
        "description-no-trigger",
        `Description states no triggering condition (e.g. "Use when …"), so the skill will under-fire.`,
      );
    }
  }

  // ── allowed-tools ──
  const tokens = allowedToolsFrom(fm["allowed-tools"]);
  if (tokens.length === 0) {
    add(
      "allowed-tools-missing",
      "Frontmatter declares no `allowed-tools` tokens. Every skill here grants its tools explicitly, as `Read Bash(git log:*)` or `[Read, Bash(git log:*)]`.",
    );
  } else {
    for (const token of tokens) {
      if (!ALLOWED_TOOL_RE.test(token)) {
        add(
          "allowed-tools-bad-token",
          `Invalid \`allowed-tools\` token ${JSON.stringify(token)}. Expected \`Read\` or \`Bash(git log:*)\`.`,
        );
      }
    }
    if (!tokens.some((token) => MULTIWORD_SCOPE_RE.test(token))) {
      // Pack convention: each skill runs a real scoped command, and the scope
      // is written as the command actually reads. It doubles as the standing
      // proof that this linter tokenizes the field rather than splitting it.
      add(
        "allowed-tools-no-multiword-scope",
        "No `allowed-tools` scope contains a space (e.g. `Bash(git log:*)`). " +
          "Every skill in this pack runs a scoped command; write the scope as the command reads.",
      );
    }
  }

  // ── layout ──
  if (!files.some((file) => file.startsWith("scripts/"))) {
    add("scripts-missing", "No `scripts/` file. The mechanical half of a skill is a script, not prose.");
  }
  if (files.some((file) => file.startsWith("assets/"))) {
    add(
      "assets-present",
      "Has an `assets/` file. Assets do not survive a GitHub sync, so a skill depending on one cannot round-trip.",
    );
  }

  // No rule here checks trigger tests, and their absence from this repository
  // is deliberate rather than an oversight. A skill's fire and skip cases are
  // authored and run in Contexory, against a live dispatcher with every sibling
  // skill competing for the same prompt — which is the only setting in which
  // over-triggering shows up at all, and not something a file in a git
  // repository can assert. Those cases are not public: each skill's README says
  // so rather than pointing at a page that would not carry them.

  return problems;
}

// ── The filesystem half ───────────────────────────────────────────────────

/** Every file under `dir`, as POSIX-relative paths. */
function filesUnder(dir, prefix = "") {
  const found = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) found.push(...filesUnder(join(dir, entry.name), rel));
    else found.push(rel);
  }
  return found.sort();
}

function isFile(...parts) {
  try {
    return statSync(join(...parts)).isFile();
  } catch {
    return false;
  }
}

const childDirs = (dir) =>
  readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && !entry.name.startsWith("."))
    .map((entry) => entry.name)
    .sort();

/**
 * Every child directory of `pack` holding a SKILL.md, sorted.
 *
 * Skills live at `<pack>/<skill>/`, never at the repository root. The extra
 * level is deliberate and permanent: a second pack is then purely additive,
 * where a flat root would force every existing skill to move — and these URLs
 * are the ones submitted to skill-ranking sites, so moving them later breaks
 * links we do not control.
 */
export function skillDirs(root, pack) {
  const base = pack ? join(root, pack) : root;
  return childDirs(base).filter((name) => isFile(base, name, "SKILL.md"));
}

/** Every child directory of `root` that holds at least one skill. */
export function packDirs(root) {
  return childDirs(root).filter((name) => skillDirs(root, name).length > 0);
}

// ── gallery links ─────────────────────────────────────────────────────────

export const GALLERY_LINKS_FILE = "gallery-links.json";

/** `https://<host>/skills/<org>/<publicSlug>` and nothing else. */
const GALLERY_URL_RE = /^https:\/\/[^/\s]+\/skills\/[a-z0-9-]+\/[a-z0-9-]+$/;

/**
 * Check the skill → gallery-URL mapping.
 *
 * The mapping is a checked-in file rather than a derivation, because a gallery
 * URL cannot be derived. `publicSlug` is allocated once, on a skill's first
 * publish, and is never re-derived afterwards — it is a permalink, and its
 * allocation can even land on a different value than the title suggests when
 * two same-titled skills race for it. So the slug is a fact to be recorded
 * after publishing, not computed before.
 *
 * `null` means "not published yet", which is a legitimate state and the one
 * this repository ships in until the gallery is seeded. What is *not* legitimate
 * is a skill missing from the file entirely: that is how a skill silently ships
 * with no link and nobody notices. Flipping `status` to `published` turns every
 * remaining `null` into a failure.
 */
export function lintGalleryLinks(root, skills) {
  const at = (code, message) => [{ dir: GALLERY_LINKS_FILE, code, message }];
  const path = join(root, GALLERY_LINKS_FILE);
  if (!isFile(path)) {
    return at("gallery-links-missing", `${GALLERY_LINKS_FILE} is missing.`);
  }

  let parsed;
  try {
    parsed = JSON.parse(readFileSync(path, "utf8"));
  } catch (err) {
    return at("gallery-links-unparsed", `${GALLERY_LINKS_FILE} is not valid JSON: ${err.message}`);
  }

  const problems = [];
  const status = parsed?.status;
  if (status !== "pending" && status !== "published") {
    problems.push(...at("gallery-links-status", `\`status\` must be "pending" or "published", got ${JSON.stringify(status)}.`));
  }
  const links = parsed?.links ?? {};

  for (const skill of skills) {
    if (!Object.hasOwn(links, skill)) {
      problems.push(
        ...at("gallery-link-missing", `No entry for \`${skill}\`. Add it, as a URL or as null while it is unpublished.`),
      );
      continue;
    }
    const value = links[skill];
    if (value === null) {
      if (status === "published") {
        problems.push(
          ...at("gallery-link-pending", `\`${skill}\` is still null while status is "published".`),
        );
      }
      continue;
    }
    if (typeof value !== "string" || !GALLERY_URL_RE.test(value)) {
      problems.push(
        ...at(
          "gallery-link-malformed",
          `\`${skill}\`: ${JSON.stringify(value)} is not an absolute https gallery URL (https://<host>/skills/<org>/<slug>).`,
        ),
      );
    }
  }

  for (const key of Object.keys(links)) {
    if (!skills.includes(key)) {
      problems.push(...at("gallery-link-orphan", `Entry for \`${key}\`, which is not a skill in this repository.`));
    }
  }

  return problems;
}

/** Lint every skill in every pack under `root`. */
export function lintPack(root) {
  const packs = packDirs(root);
  const problems = [];

  // A skill directly under the root is the layout mistake worth catching: it
  // would work today and force every URL to move the day a second pack lands.
  for (const dir of childDirs(root)) {
    if (isFile(root, dir, "SKILL.md")) {
      problems.push({
        dir,
        code: "skill-outside-pack",
        message: `\`${dir}/\` holds a SKILL.md at the repository root. Skills live at <pack>/<skill>/.`,
      });
    }
  }

  if (packs.length === 0) {
    problems.push({ dir: ".", code: "pack-empty", message: `No pack directory found under ${root}.` });
    // Deliberately no early return. Returning here suppressed the gallery-links
    // check in exactly the case where it says the most useful thing — which
    // skills the mapping still lists that the repository no longer has.
  }

  const allSkills = [];
  for (const pack of packs) {
    for (const skill of skillDirs(root, pack)) {
      allSkills.push(skill);
      const skillRoot = join(root, pack, skill);
      problems.push(
        ...lintSkill({
          dir: skill,
          skillMd: readFileSync(join(skillRoot, "SKILL.md"), "utf8"),
          files: filesUnder(skillRoot),
        }).map((problem) => ({ ...problem, dir: `${pack}/${skill}` })),
      );
    }
  }

  problems.push(...lintGalleryLinks(root, allSkills));
  return problems;
}

/** Entry point. Returns the process exit code rather than calling `exit`. */
export function runCli({ argv = [], cwd = process.cwd(), log = console.log, error = console.error } = {}) {
  const root = argv[0] ?? cwd;
  const problems = lintPack(root);
  if (problems.length === 0) {
    const packs = packDirs(root);
    const skills = packs.reduce((n, pack) => n + skillDirs(root, pack).length, 0);
    log(`Pack lint: ${skills} skill(s) across ${packs.length} pack(s) clean.`);
    return 0;
  }
  for (const problem of problems) error(`${problem.dir}: [${problem.code}] ${problem.message}`);
  error(`\nPack lint failed with ${problems.length} problem(s).`);
  return 1;
}
