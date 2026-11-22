---
name: style-review
description: Review a LaTeX file against guidelines/style.md and present a report of deterministic violations and rubric-based judgment, then interactively apply user-selected fixes.
---

Review adherence of a LaTeX file to `guidelines/style.md`. Produces a structured report of deterministic rule violations (em-dashes, banned words, author-name citations, prose semicolons) and rubric-based judgment scores on voice, rhythm, vocabulary, paragraph discipline, and argument structure. Presents the report, then interactively asks the user which fix categories to apply before applying any edits.

Takes a single path argument: the `.tex` file to review. Reads `guidelines/style.md` from the project root. Writes no files other than the `Edit`-tool modifications to the target `.tex` file itself, and only after user confirmation.

## Steps

1. **Parse the input.** Extract the target file path from the skill arguments. Use Bash `test -f {path} && echo OK || echo MISSING` to confirm it exists. If missing, print an error and stop. Confirm the path ends in `.tex`; if not, print a warning but continue (the user may be reviewing a `.tex.in` template or similar).

2. **Read `guidelines/style.md`.** Use Bash `test -f guidelines/style.md && echo OK || echo MISSING`. If missing, print `error: guidelines/style.md not found at project root` and stop. Use Read to load its full contents.

3. **Extract the banned phrase list dynamically.** Parse two sections of the style guide:

   From `## 11. Anti-Patterns (What to Avoid)`, collect bullet items under:
   - `### Filler phrases to never use`
   - `### Hedging patterns to never use`
   - `### Enthusiasm patterns to never use`

   From `## 5. Transitions and Connectors`, collect bullet items under:
   - `### Transitions the author avoids`

   Note that these subsections are not all in the same top-level section. Find each subsection by its exact `###` heading.

   The bullet items in `style.md` are formatted as `- "phrase..." (annotation)`. The annotation often contains quoted counter-examples of the author's *preferred* replacement (e.g., `uses "Recall that" instead`), so the trailing parenthetical must be stripped BEFORE extracting quoted phrases. Otherwise the preferred replacement would be mis-extracted as a banned phrase.

   Apply this algorithm per bullet:

   1. Strip the leading `- ` list marker.
   2. Strip backtick, bold (`**`), and italic (`*`) formatting globally.
   3. Strip the trailing parenthetical annotation: remove everything from the first ` (` onward if there is no later `)` followed by more quoted content. A simple and sufficient rule: `re.sub(r"\s*\([^)]*\)\s*$", "", line)` applied repeatedly (to handle nested-parenthesis annotations, though these are rare).
   4. Now extract every `"([^"]*)"` substring from the remaining text. Each captured group is a candidate phrase. A single bullet may produce multiple candidates (e.g., `"Groundbreaking" / "Revolutionary" / "Paradigm-shifting"` yields three).
   5. For each candidate, strip:
      - Trailing ellipsis (`...` or `…`) — these are wildcards indicating "any continuation", not literal text.
      - Surrounding whitespace.
   6. Preserve a trailing comma if present (phrases like `Moreover,` and `Interestingly,` are meaningful with the comma).
   7. Drop any candidate shorter than 3 characters (likely not a real phrase).

   After processing all bullets, **deduplicate** the phrase list case-insensitively, keeping the first-seen casing.

   If the final deduplicated list has fewer than 20 entries, print `warning: extracted N banned phrases from style.md — check section format` and continue. Keep the core phrases as case-insensitive match targets for the scan in step 5.

   **Alternatives table for swap suggestions** (hardcoded inside this skill — phrases not in this table are flag-only, no auto-swap):

   ```
   delve                        → examine
   delving                      → examining
   delved                       → examined
   delves                       → examines
   utilize                      → use
   utilizes                     → uses
   utilizing                    → using
   utilized                     → used
   facilitate                   → enable
   facilitates                  → enables
   facilitating                 → enabling
   facilitated                  → enabled
   novel                        → new
   plays a crucial role         → is central
   it is important to note that → Note that
   it is worth noting that      → Note that
   it should be noted that      → Note that
   in recent years,             → (delete)
   interestingly,               → (delete)
   notably,                     → (delete)
   importantly,                 → (delete)
   remarkably,                  → (delete)
   impressively,                → (delete)
   it appears that              → (delete)
   arguably,                    → (delete)
   arguably                     → (delete)
   to some extent               → (delete)
   one could argue that         → (delete)
   cutting-edge                 → advanced
   groundbreaking               → significant
   ```

   "(delete)" means the phrase should be removed, but the skill does NOT auto-delete — it flags as report-only for human review, because deleting a word may leave ungrammatical fragments.

4. **Build a prose view of the target file.** Use Bash to run this Python heredoc, which produces a line-aligned prose-stripped copy of the file at `$TMPDIR/style-review-prose.txt`:

   ```bash
   TEX_FILE="<path from step 1>"
   PROSE_FILE="$TMPDIR/style-review-prose.txt"
   python3 - "$TEX_FILE" "$PROSE_FILE" <<'PY'
   import re, sys
   src = open(sys.argv[1]).read()
   lines = src.split("\n")
   out = []
   in_verbatim = False
   for line in lines:
       if re.search(r"\\begin\{(verbatim|lstlisting|minted)\}", line):
           in_verbatim = True
       if in_verbatim:
           out.append("")
           if re.search(r"\\end\{(verbatim|lstlisting|minted)\}", line):
               in_verbatim = False
           continue
       # Strip line comments (respect escaped \%)
       line = re.sub(r"(?<!\\)%.*$", "", line)
       # Strip \cite{...}, \ref{...}, \label{...}, \eqref{...}, \cref{...}, \Cref{...}
       line = re.sub(r"\\(cite|ref|eqref|label|cref|Cref|citep|citet|autoref|nameref)\{[^}]*\}", "", line)
       # Unwrap \textbf{x}, \textit{x}, \emph{x}, \textsc{x}, \textrm{x} — keep inner text
       line = re.sub(r"\\(textbf|textit|emph|textsc|textrm|textsf|texttt)\{([^}]*)\}", r"\2", line)
       # Strip remaining LaTeX commands that take a brace argument
       line = re.sub(r"\\[a-zA-Z]+\*?\s*\{[^}]*\}", "", line)
       # Strip bare LaTeX commands like \name, \\, etc.
       line = re.sub(r"\\[a-zA-Z]+\*?", "", line)
       line = re.sub(r"\\\\", "", line)
       # Strip inline math
       line = re.sub(r"\$[^$]*\$", "", line)
       out.append(line)
   open(sys.argv[2], "w").write("\n".join(out))
   PY
   ```

   This is line-number-preserving: every input line produces exactly one output line, so Pass 1 grep line numbers match the original file.

5. **Pass 1 — deterministic grep scan.** Scan the prose view for each violation class. Collect all findings into an in-memory structure: `{rule, line, original, context, suggested_fix}`.

   (a) **Banned phrases.** For each phrase from step 3's extracted list, scan the prose view with a case-insensitive literal match. Anchor with word boundaries where the phrase starts and ends with an alphanumeric character (e.g., match `novel` as `\bnovel\b`, but match `Interestingly,` without a trailing boundary because the comma is already a non-word character). Use Grep with `-n -i -o` and an appropriate regex pattern. Record each hit as `{rule: "banned-word", line: N, original: <matched text>, context: <8 words around>, suggested_fix: <from alternatives table or null>}`.

   (b) **Em-dashes.** Run three Grep passes in order to avoid double-counting: first for `---` (LaTeX em-dash), then for `--` (LaTeX en-dash, also banned), then for `—` (U+2014 em-dash). Record each as `{rule: "em-dash", line, original, context}`. For each, compute the suggested fix: if the character immediately after the dash (skipping spaces) is a capital letter, suggest replacing the dash with `. ` and capitalizing the next word; otherwise suggest replacing with `, `.

   (c) **Author-name citations.** Run Grep with this regex (ripgrep syntax):

   ```
   \b[A-Z][a-z]+(?: and [A-Z][a-z]+)?(?: et al\.?)?\s+(?:show|shows|demonstrate|demonstrates|propose|proposes|argue|argues|find|finds|report|reports|prove|proves|claim|claims|observe|observes)\b
   ```

   **Exclude false positives**: discard any hit whose leading word is one of the following stopwords (pronouns, determiners, sentence starters, and style-guide preferred verbs that happen to match): `We, Our, Us, I, The, This, These, Those, That, Here, There, Thus, Hence, However, Note, Observe, Recall, Consider, Suppose, Let, It, They, One, Some, Many, Most, All, Both, Either, Neither, Such, What, When, Where, Why, How, Which, Who, First, Second, Third, Next, Finally, Still, Yet, Also, Again`. These are never author names.

   For each remaining hit, record `{rule: "author-cite", line, original, context, suggested_fix: "remove attributive clause"}`.

   (d) **Prose semicolons.** Run Grep for `; ` (semicolon followed by a space) in the prose view. Since verbatim blocks and inline math are already stripped, every remaining hit is a prose semicolon. Record each as `{rule: "semicolon", line, original, context, suggested_fix: "split into two sentences"}`.

   Sort all findings by `(line, rule)`. Print a summary count per rule.

6. **Pass 2 — Opus judgment agent.** Launch one Agent with `model: "opus"` and the prompt template below. Substitute `{STYLE_MD}` with the full contents of `guidelines/style.md`, `{TEX_NUMBERED}` with the target file prefixed by `NNN: ` line numbers (use Bash `awk '{printf "%03d: %s\n", NR, $0}' "$TEX_FILE"`), and `{PASS1_JSON}` with a compact list of Pass 1 findings:

   > You are a style compliance reviewer for academic writing. Your task is to score a LaTeX file against a specific author's writing style guide and produce a structured rubric report.
   >
   > **Author style guide (full contents of `guidelines/style.md`):**
   >
   > {STYLE_MD}
   >
   > **Target file (line-numbered):**
   >
   > ```
   > {TEX_NUMBERED}
   > ```
   >
   > **Deterministic violations already found by the grep pass — do NOT re-flag these:**
   >
   > ```
   > {PASS1_JSON}
   > ```
   >
   > Score the file 1 to 5 on each of the following ten axes. For each, provide 1-2 lines of justification and reference specific line numbers where the file exemplifies or violates the rule. For every axis scoring 3 or below, provide at least one concrete rewrite suggestion with the original line and the proposed rewrite.
   >
   > 1. **Voice and tone** — confident and matter-of-fact; not promotional, not apologetic.
   > 2. **Sentence rhythm** — sentence length varies with purpose: long sentences carry mechanisms, short ones carry conclusions. Penalize long runs of uniform-length sentences.
   > 3. **Clause ordering** — condition or cause first for mechanisms ("Since X, Y"); concession first, then the pivot ("While X, Y").
   > 4. **Topic sentence discipline** — paragraphs open with the claim, never with wind-up or background.
   > 5. **Word choice** — plain words over inflated ones; one word per concept, no synonym rotation within a paragraph.
   > 6. **Connector usage** — a small set of connectors reused consistently; no filler transitions.
   > 7. **Paragraph closings** — consequence, forward pointer, or quantitative verdict; never a restatement of the opening sentence.
   > 8. **Quantitative precision** — numbers replace evaluative adjectives ("38% lower tail latency", not "significantly lower latency").
   > 9. **Citation style** — findings are cited directly, not attributed by author name ("work by Foo shows...").
   > 10. **Argument structure** — prior work is named and cited with its specific property, never alluded to; limitations are stated and bounded; claims are followed immediately by evidence. Score only the parts present in the file.
   >
   > **Output format — strict. Output only these two sections, nothing else:**
   >
   > ```
   > RUBRIC_SCORES
   > 1. Voice and tone: X/5 — <one-line justification, optional line refs>
   > 2. Sentence rhythm: X/5 — <one-line justification, optional line refs>
   > 3. Clause ordering: X/5 — <one-line justification>
   > 4. Topic sentence discipline: X/5 — <one-line justification>
   > 5. Word choice: X/5 — <one-line justification>
   > 6. Connector usage: X/5 — <one-line justification>
   > 7. Paragraph closings: X/5 — <one-line justification>
   > 8. Quantitative precision: X/5 — <one-line justification>
   > 9. Citation style: X/5 — <one-line justification>
   > 10. Argument structure: X/5 — <one-line justification>
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

7. **Assemble and print the report.** Combine Pass 1 findings with the Pass 2 rubric and rewrite suggestions. Compute:
   - Deterministic violations: total count across all four rules.
   - Rubric mean: arithmetic mean of the 10 Pass 2 scores, printed as `X.X / 5`.

   Print the report to the conversation in this exact format:

   ```
   # Style Review — <tex_path>

   ## Compliance summary
   - Deterministic violations: N (banned-word: N, em-dash: N, author-cite: N, semicolon: N)
   - Rubric mean: X.X / 5

   ## Deterministic violations (N)
   1. [<rule>] line <N>: "<original>" (in "<context>")
      Suggested fix: <suggested_fix or "manual rewrite needed">
   ...

   ## Rubric scores
   <Pass 2 RUBRIC_SCORES section verbatim>

   ## Judgment-based rewrite suggestions
   <Pass 2 REWRITE_SUGGESTIONS section verbatim>
   ```

8. **Interactive fix selection.** Use AskUserQuestion with one question, `multiSelect: true`, and five options:

   - Label: "Banned words" — description: "Apply alternatives-table swaps for banned-word findings that have a suggested fix. Report-only flags (where the suggested fix is '(delete)') stay in the report."
   - Label: "Em-dashes" — description: "Replace every em-dash ('---', '--', '—') in prose with either a period + capitalized next word or a comma, based on context."
   - Label: "Author-name citations" — description: "Rewrite 'Foo et al. show X [key]' to 'X [key]' by removing the attributive clause. Skip constructions the skill cannot safely rewrite."
   - Label: "Prose semicolons" — description: "Split sentences containing a semicolon into two sentences, capitalizing the following letter."
   - Label: "Judgment rewrites" — description: "Apply the Pass 2 REWRITE_SUGGESTIONS verbatim: replace each Original span with its Proposed rewrite. Skip any whose Original text is no longer unique in the file after prior fixes."

   The question text: "Which fix categories should I apply? Deterministic fixes are mechanical; judgment rewrites come from the Pass 2 agent and replace an Original span with its Proposed rewrite."

   If the user selects zero options, print `No fixes applied.` and exit.

9. **Apply selected fixes.** For each selected category, iterate through the Pass 1 findings for that rule and apply an `Edit` for each. Skip findings whose `suggested_fix` is `(delete)` or `null`.

   (a) **Banned words.** For each finding:
   - Build `old_string` by taking 2-3 words before and after the matched phrase from the prose view at the flagged line. Verify uniqueness in the original file by Grep-counting. If non-unique, widen the context until unique or give up after 2 retries.
   - Build `new_string` by applying the alternatives-table swap with case preservation: if the original first letter is uppercase, capitalize the replacement; otherwise keep lowercase.
   - Call the Edit tool with the original file path, `old_string`, `new_string`, `replace_all: false`.
   - On failure (non-unique, not found), record as `needs manual fix`.

   (b) **Em-dashes.** For each finding:
   - Build `old_string` with 2-3 words of context surrounding the dash.
   - Build `new_string`: replace `---`/`--`/`—` with either `. ` + capitalized next word (if the next word starts with uppercase) or `, ` (otherwise).
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

10. **Re-scan and final report.** After all selected fixes are applied, re-run the Pass 1 scan on the (now-modified) target file. Print:

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

- The skill never commits, never touches `ref.bib`, never updates memory, never modifies `guidelines/style.md`.
- If `guidelines/style.md`'s anti-pattern section format changes, step 3's extraction will likely return an empty or partial list; the skill prints `warning: extracted N banned phrases from style.md — check section ## 11 format` if N < 20.
- The skill does NOT re-run after fixes are applied; a second pass would require a second user confirmation. Users who want iterative cleanup should re-invoke `/paper-writer:style-review`.
