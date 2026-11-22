---
name: style-review
description: Review a LaTeX file against the project's style profile, report deterministic violations and rubric-based judgment scores, then interactively apply user-selected fixes.
---

Review a LaTeX file against the active style profile. Produces a structured report of deterministic rule violations (banned phrases, plus em-dashes, author-name citations and prose semicolons when the profile's rules check them) and judgment scores on each axis of the profile's rubric. Presents the report, then interactively asks the user which fix categories to apply before applying any edits.

Takes a single path argument: the `.tex` file to review. Writes no files other than the `Edit`-tool modifications to the target `.tex` file itself, and only after user confirmation.

## Configuration

Before step 1, resolve the style profile:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" style resolve
```

It prints JSON with `source` (`project`, `user`, `legacy` or `baseline`), `style_md`, `rubric_md` and `overrides_md` (may be null). Throughout this skill, `{style.style_md}`, `{style.rubric_md}` and `{style.overrides_md}` stand for those paths. Print any `note:` lines to the user, for example that no profile is configured and the plugin baseline is in use. Run commands from the project root.

## Steps

1. **Parse the input.** Extract the target file path from the skill arguments. Use Bash `test -f {path} && echo OK || echo MISSING` to confirm it exists. If missing, print an error and stop. Confirm the path ends in `.tex`; if not, print a warning but continue (the user may be reviewing a `.tex.in` template or similar).

2. **Pass 1: deterministic scan.** Run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" style scan "<path from step 1>"
   ```

   The scan applies the profile's merged rules (plugin defaults, then the profile's `rules.toml`, then any project overrides) to a prose view of the file: comments, verbatim blocks, inline math, `\cite`/`\ref`-style commands and other LaTeX markup are stripped, and line numbers match the original file. It prints JSON:

   - `summary`: counts per rule (`banned-word`, `em-dash`, `author-cite`, `semicolon`) and `total`.
   - `findings`: one object per violation, sorted by line: `{rule, line, col, original, context, suggested_fix, level}`.
     - `suggested_fix` is the replacement text, `(delete)` for phrases that should be removed by hand, or `null` when there is no mechanical fix.
     - `level` is `forbid` (fixable in step 6) or `warn` (report only).

   Keep the findings in memory for the report and for step 6. If the command fails, print its error and stop.

3. **Pass 2: judgment agent.** Use Read to load `{style.style_md}`, `{style.rubric_md}`, and `{style.overrides_md}` if it is not null. Launch one Agent with `model: "opus"` and the prompt template below. Substitute `{STYLE_MD}` with the full style guide followed by the overrides (if any) under a heading "Per-project overrides (take precedence)", `{RUBRIC}` with the full rubric, `{N}` with the number of rubric axes, `{TEX_NUMBERED}` with the target file prefixed by `NNN: ` line numbers (use Bash `awk '{printf "%03d: %s\n", NR, $0}' "$TEX_FILE"`), and `{PASS1_JSON}` with a compact list of the Pass 1 findings:

   > You are a style compliance reviewer for academic writing. Your task is to score a LaTeX file against a specific writing style guide and produce a structured rubric report.
   >
   > **Style guide:**
   >
   > {STYLE_MD}
   >
   > **Target file (line-numbered):**
   >
   > ```
   > {TEX_NUMBERED}
   > ```
   >
   > **Deterministic violations already found by the scan — do NOT re-flag these:**
   >
   > ```
   > {PASS1_JSON}
   > ```
   >
   > Score the file 1 to 5 on each of the following {N} axes. Where an axis refers to a section of the style guide, use that section. For each, provide 1-2 lines of justification and reference specific line numbers where the file exemplifies or violates the rule. For every axis scoring 3 or below, provide at least one concrete rewrite suggestion with the original line and the proposed rewrite.
   >
   > {RUBRIC}
   >
   > **Output format — strict. Output only these two sections, nothing else:**
   >
   > ```
   > RUBRIC_SCORES
   > 1. <axis name>: X/5 — <one-line justification, optional line refs>
   > 2. <axis name>: X/5 — <one-line justification, optional line refs>
   > ... one line per axis, in rubric order ...
   >
   > REWRITE_SUGGESTIONS
   > A. Line <N> — <rule name>
   >    Original: "<exact text>"
   >    Proposed: "<rewrite>"
   >
   > B. Line <N> — <rule name>
   >    Original: "<exact text>"
   >    Proposed: "<rewrite>"
   > ```
   >
   > Do not include any preamble, explanation, or markdown headings outside the two sections above.

   Capture the agent's output. Parse the `RUBRIC_SCORES` section into a list of (axis, score, justification) tuples. Parse the `REWRITE_SUGGESTIONS` section as a list of (letter, line, rule, original, proposed).

4. **Assemble and print the report.** Combine the Pass 1 findings with the Pass 2 rubric and rewrite suggestions. Compute:
   - Deterministic violations: `total` from the scan, with the per-rule `summary` counts.
   - Rubric mean: arithmetic mean of the Pass 2 scores, printed as `X.X / 5`.

   Print the report to the conversation in this exact format:

   ```
   # Style Review — <tex_path>

   ## Compliance summary
   - Style profile: <source> (<style_md>)
   - Deterministic violations: N (banned-word: N, em-dash: N, author-cite: N, semicolon: N)
   - Rubric mean: X.X / 5

   ## Deterministic violations (N)
   1. [<rule>] line <N>: "<original>" (in "<context>")
      Suggested fix: <suggested_fix or "manual rewrite needed"><" (report only)" if level is warn>
   ...

   ## Rubric scores
   <Pass 2 RUBRIC_SCORES section verbatim>

   ## Judgment-based rewrite suggestions
   <Pass 2 REWRITE_SUGGESTIONS section verbatim>
   ```

5. **Interactive fix selection.** Use AskUserQuestion with one question, `multiSelect: true`. Offer one option per category below that has at least one fixable finding (`level: forbid`), plus "Judgment rewrites" if Pass 2 produced any:

   - Label: "Banned words" — description: "Apply the suggested swap for banned-word findings that have one. Report-only flags (where the suggested fix is '(delete)') stay in the report."
   - Label: "Em-dashes" — description: "Replace every em-dash ('---', '--', '—') in prose with either a period + capitalized next word or a comma, based on context."
   - Label: "Author-name citations" — description: "Rewrite 'Foo et al. show X [key]' to 'X [key]' by removing the attributive clause. Skip constructions the skill cannot safely rewrite."
   - Label: "Prose semicolons" — description: "Split sentences containing a semicolon into two sentences, capitalizing the following letter."
   - Label: "Judgment rewrites" — description: "Apply the Pass 2 REWRITE_SUGGESTIONS verbatim: replace each Original span with its Proposed rewrite. Skip any whose Original text is no longer unique in the file after prior fixes."

   AskUserQuestion allows at most four options. If all five apply, ask about the four deterministic categories first, then ask a second single-option question about judgment rewrites.

   The question text: "Which fix categories should I apply? Deterministic fixes are mechanical; judgment rewrites come from the Pass 2 agent and replace an Original span with its Proposed rewrite."

   If the user selects zero options, print `No fixes applied.` and exit.

6. **Apply selected fixes.** For each selected category, iterate through the Pass 1 findings for that rule and apply an `Edit` for each. Skip findings whose `suggested_fix` is `(delete)` or `null`, and findings whose `level` is `warn` (those are report only).

   (a) **Banned words.** For each finding:
   - Build `old_string` by taking 2-3 words before and after the matched phrase from the original file at the flagged line. Verify uniqueness in the original file by Grep-counting. If non-unique, widen the context until unique or give up after 2 retries.
   - Build `new_string` by replacing the matched phrase with the finding's `suggested_fix` (the scan has already matched the original's capitalization).
   - Call the Edit tool with the original file path, `old_string`, `new_string`, `replace_all: false`.
   - On failure (non-unique, not found), record as `needs manual fix`.

   (b) **Em-dashes.** For each finding:
   - Build `old_string` with 2-3 words of context surrounding the dash.
   - Build `new_string`: replace `---`/`--`/`—` with the finding's `suggested_fix`. If it is `. `, capitalize the next word.
   - Call Edit. Record failures.

   (c) **Author-name citations.** For each finding:
   - Extract the attributive clause via regex: `\b[A-Z][a-z]+( and [A-Z][a-z]+)?( et al\.?)? (show|shows|demonstrate|demonstrates|propose|proposes|argue|argues|find|finds|report|reports|prove|proves|claim|claims|observe|observes) that `
   - If the match includes "that ", the `new_string` omits the entire clause up through "that " and capitalizes the following word.
   - If the match does not include "that " (e.g., `Foo et al. show X`), the rewrite is harder; skip and mark `needs manual fix`.
   - Call Edit with 3 words of leading context preserved.

   (d) **Prose semicolons.** For each finding:
   - Build `old_string` with 2-3 words of context around the `; `.
   - Build `new_string` by replacing `; ` with `. ` and capitalizing the following letter.
   - Call Edit. Record failures.

   (e) **Judgment rewrites.** Apply this category **after** (a)–(d), so deterministic edits have already landed before the Pass 2 spans are touched. For each parsed `(letter, line, rule, original, proposed)` tuple from Pass 2's REWRITE_SUGGESTIONS:
   - Use `original` as `old_string` and `proposed` as `new_string`. Call Edit with `replace_all: false`.
   - On non-unique match, widen `old_string` by prepending the preceding word from the target line and retry once. If still non-unique, record as `needs manual fix`.
   - On not-found (likely because an earlier deterministic fix already mutated the span), record as `needs manual fix` and continue.

   Tally: `<applied> / <attempted>` for each category.

7. **Re-scan and final report.** After all selected fixes are applied, re-run the step 2 scan command on the (now-modified) target file. Print:

   ```
   ## Fixes applied
   - Banned words: N/M
   - Em-dashes: N/M
   - Author-name citations: N/M
   - Prose semicolons: N/M
   - Judgment rewrites: N/M

   ## Remaining deterministic violations: N
   <list any remaining>
   ```

   Do not re-run Pass 2. The user already has the rubric scores and rewrite suggestions from the initial report.

## Notes

- The skill never commits, never touches the bibliography, never updates memory, and never modifies the style profile.
- Which deterministic rules run, which phrases are banned, and which swaps are suggested all come from the profile's `rules.toml` merged over the plugin defaults. To change them, edit the profile or add a project `style-overrides.toml`, not this skill.
- The skill does NOT re-run after fixes are applied; a second pass would require a second user confirmation. Users who want iterative cleanup should re-invoke `/paper-writer:style-review`.
