---
name: write-background
description: Write the background section for the paper
---

# Paper background writing

## Overview

Write the "Background and Motivation" section of an academic paper in LaTeX, given an outline describing the topic background and motivation challenges. You are a professor of computer science and engineering writing for a top conference in your field. Provide comprehensive background context and clearly articulate each motivation challenge in its own paragraph. Do not ramble.

Takes an outline as input (text or file path in `$ARGUMENTS`). Reads the writing style guide, search results referenced in the outline, and the project's main LaTeX file. Writes output to `{paths.paper_dir}/background.tex` (overwriting if it already exists) and creates or updates `{paths.bib}`.

**Strict adherence to `{style.style_md}` is mandatory and non-negotiable.** Every sentence produced by this skill must conform to the style guide's voice, vocabulary, rhythm, paragraph structure, and anti-patterns. A draft that uses a banned phrase or a forbidden construction from the style rules is a defect, not an acceptable output. The style guide must be considered for every word, every sentence, every paragraph — not just loaded once and forgotten.

## Configuration

Before step 1, resolve the project configuration:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" config dump
```

It prints the project's `paper-writer.toml` settings as JSON, or the defaults when the project has none. Throughout this skill, `{paths.*}`, `{paper.*}` and `{venues.*}` stand for values from that output: substitute them before running any command or writing any prompt. Lists such as `{paper.target_venues}` are written comma-separated. Run commands from `project_root`.

Then resolve the style profile and its rules:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" style resolve
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" style rules
```

`{style.style_md}`, `{style.overrides_md}` and `{style.rubric_md}` stand for the `style_md`, `overrides_md` and `rubric_md` paths from `style resolve`. `{style.overrides_md}` may be null, in which case skip every step that mentions it. Print any `note:` lines from these commands to the user (for example, that the plugin baseline style is in use). From `style rules`, `{rules.banned}` is the combined `phrases.banned` and `phrases.avoided_transitions` lists, and `{rules.forbidden}` is the list of `deterministic` rules set to `forbid` or `warn`, written as: em-dashes (`---`, `--`, `—`) for `em_dash`, author-name citations ("Smith et al. show...") for `author_name_citations`, and prose semicolons for `prose_semicolons`.

## Steps

1. **Parse the outline.** Extract the outline from `$ARGUMENTS`. If it looks like a file path (contains `/` or ends in `.md` or `.txt`), read it with Read. Otherwise treat the argument text as the outline itself. Check whether the outline specifies a page length instruction (e.g., "Length: 1.5 pages" or similar). If present, use that target length. Otherwise default to approximately 1 page (~600-800 words for ACM two-column format). Also check whether the outline specifies a custom section title; if not, use "Background and Motivation."

2. **Validate prerequisites.** Use Bash to check that the paper's main LaTeX file exists: `test -f {paths.main_tex} && echo OK || echo MISSING`. If MISSING, print an error telling the user that `{paths.main_tex}` is required (run `/paper-writer:init` to create a project), and **stop**. Then verify the outline contains at least one of: a Background subsection or a Motivation subsection. If neither is present, print an error and **stop**.

3. **Set up system name commands.** Run `/paper-writer:paper-name` (follow the steps in that skill) to extract the system name from `{paths.main_tex}` and ensure the LaTeX name commands (`\name`, `\names`, `\boldname`, `\bigname`) are defined. This also writes `{paths.name_commands}` with prompt instructions for the writing agent.

4. **Read shared context.** Read the following files. These will be passed to sub-agents in later steps.

   - Use Read to load `{style.style_md}`. If `{style.overrides_md}` is set, Read it too: it holds per-project adjustments that take precedence over the guide. Together they are the **binding style contract** for every sentence this skill produces — voice, sentence rhythm, vocabulary, connectors, paragraph structure, and anti-patterns. All prose written in later steps must conform to this guide without exception. Do not fall back to any other style rules.
   - Use Read to load `{paths.main_tex}`. Note its document class, its `\bibliographystyle{...}` and its `\bibliography{...}` file, so the new section and BibTeX entries match them. Use the BibTeX entry format shown in step 8.
   - Use Bash: `mkdir -p {paths.paper_dir} && test -f {paths.bib} && echo EXISTS || echo NEW`. If it exists, use Read to load its contents. Parse existing BibTeX keys and DOIs so they can be reused rather than duplicated.
   - Use Read to load `{paths.name_commands}`. This will be included in the Opus writing prompt.

5. **Select citations.** Parse the outline to identify contexts where citations are needed (marked by "Citation required" or similar pointers, or by explicit paper title references in backticks or brackets). For each citation context, determine the criteria type:

   - For Background contexts (providing supporting evidence, examples, or technical details about the topic): create a context with `CRITERIA: reason`, using the background topic as the label, the relevant description from the outline as the description, and the search result file paths referenced by that context.
   - For Motivation contexts (identifying limitations and challenges with existing approaches): create a context with `CRITERIA: gap`, using each motivation challenge as the label, the challenge description as the description, and the search result file paths referenced by that context.

   Launch one **Sonnet** Agent per citation context, **all in parallel in a single message**. Use `model: "sonnet"` for each agent. Use the prompt templates from `/paper-writer:find-citations` step 3 (the `reason` template for background contexts, the `gap` template for motivation contexts), substituting the context-specific values. Each agent selects 2-4 papers.

6. **Collect citations and assign BibTeX keys.** Follow the `/paper-writer:find-citations` deduplication and key assignment process (step 4 of that skill). Deduplicate by DOI. Assign `AuthorYY` format keys, reusing existing keys from `{paths.bib}` where DOIs match. Resolve collisions with lowercase letter suffixes (e.g., `Cao21a`, `Cao21b`).

   Build a **citation plan**: a mapping of each background topic and motivation challenge to its citation keys, plus the full BibTeX metadata for each paper.

7. **Write the complete Background and Motivation section.** Use Bash to run `mkdir -p {paths.paper_dir}`. Launch a single **Opus** Agent with `model: "opus"` to write the entire section. Provide this prompt:

   > You are writing the Background and Motivation section of an academic paper targeting a top venue in {paper.field} (e.g., {paper.target_venues}). Write the complete section as a single, coherent piece.
   >
   > **Full outline:**
   > {Paste the complete outline text}
   >
   > **Citation plan:**
   > {For each background topic, list: topic label, and for each citation: BibTeX key, paper title, and the 1-sentence reason from step 4}
   > {For each motivation challenge, list: challenge label, and for each citation: BibTeX key, paper title, and the 1-sentence gap description from step 4}
   >
   > **Name commands (follow strictly):**
   > {Paste the full contents of {paths.name_commands}}
   >
   > **NON-NEGOTIABLE STYLE CONTRACT — READ THIS BEFORE WRITING ANYTHING:**
   >
   > The writing style guide pasted below is the single source of truth for tone, vocabulary, sentence rhythm, paragraph structure, connectors, and forbidden phrases. It is a binding contract, not a suggestion. Every paragraph, every sentence, every word choice must conform to it. Consider the style guide while writing every sentence — do not load it once and forget it. Before you output the final LaTeX, re-read the guide's anti-patterns and the hard-reject list below, and verify that your draft contains none of them. Any violation is a defect that must be rewritten, not shipped.
   >
   > **Writing style (binding contract — violations are defects that must be rewritten):**
   > {Paste the full contents of {style.style_md}}
   >
   > **Per-project style overrides (take precedence over the guide):**
   > {Paste the full contents of {style.overrides_md}, or omit this block if it is null}
   >
   > **Hard-reject list (never use these phrases):** {rules.banned}
   >
   > **Forbidden constructions:** {rules.forbidden}
   >
   > **Structure -- follow this order exactly:**
   >
   > 1. `\section{section_title}` where the section title is the one parsed in step 1 (default: "Background and Motivation"). Use `\subsection` for the two main subsections.
   >
   > 2. **Background subsection** (`\subsection{...}`): Use a declarative subsection header that states the topic conclusion rather than a generic label (e.g., "How Datacenter Transports Share Bandwidth" rather than "Background"). Provide context on the topic: examples of how it is applied in practice, usage guidelines, performance or behavior in real-world usage, workflow or user guides. Use bold-label paragraph openers (`\textbf{Label.}`) for each major concept or stage being described. Use `\cite{key}` references from the citation plan where they support the argument.
   >
   > 3. **Motivation subsection** (`\subsection{...}`): Use a declarative subsection header that frames the challenges (e.g., "Why Rate Control Converges Slowly" rather than "Motivation"). Enumerate the challenges from the outline. For each challenge, write **one clear, concise paragraph**. Open each paragraph with a bold-label topic sentence (`\textbf{Challenge label.}`). Explain the problem directly and concisely. Use `\cite{key}` references from the citation plan where they support the argument. Do not ramble -- each paragraph should make its point and move on.
   >
   > **Rules:**
   > - Follow the writing style guide strictly: its voice, sentence rhythm, clause ordering, vocabulary and paragraph patterns.
   > - **The guide's anti-patterns, the hard-reject list and the forbidden constructions are authoritative.** Every phrase, construction or pattern they name is forbidden without exception. Do not rely on memory: consult the pasted guide and lists directly. If unsure whether a phrase is allowed, rewrite without it.
   > - **Self-check before output.** Before producing the final LaTeX, mentally walk through the draft once and verify: (a) no phrase from the hard-reject list or the guide's anti-patterns appears anywhere; (b) none of the forbidden constructions appears; (c) connectors and vocabulary follow the guide; (d) every paragraph opens with a topic sentence, not wind-up. If any check fails, rewrite the offending paragraph before outputting.
   > - If the style guide calls for bold-label paragraph openers, use `\textbf{Label.}` followed by the paragraph text.
   > - Declarative subsection headers that state conclusions, per the style guide's Background/Motivation pattern.
   > - Every `\cite{key}` must use a key from the citation plan above.
   > - Impersonal citation style: never refer to cited papers by author name. State the finding directly and attach the citation.
   > - Target length: {target_length}. Adjust proportionally if a different page length was specified.
   > - The section should earn the solution by demonstrating why the problem is hard, following the "rule out the obvious" pattern from the style guide.
   >
   > Output ONLY the LaTeX content starting with `\section{...}`. No preamble, no explanation.

   Use Write to create `{paths.paper_dir}/background.tex` with the agent's output.

8. **Write or update `{paths.bib}`.** Use Write (or Edit if appending to an existing file) to create or update `{paths.bib}`:

   - If `{paths.bib}` already existed, preserve all existing entries unchanged. Append new entries at the end.
   - For each new cited paper, write a complete `@inproceedings{key, ...}` block with these fields: `author`, `title`, `booktitle` (full venue name from search results), `year`, `doi`, `publisher` (ACM for `10.1145` DOIs, IEEE for `10.1109` DOIs). Example:

     ```bibtex
     @inproceedings{Smith25,
       author    = {Jane Smith and Wei Zhang and Priya Patel},
       title     = {Acme: Fast Congestion Control for Datacenter Networks},
       booktitle = {Proceedings of the ACM SIGCOMM 2025 Conference},
       year      = {2025},
       doi       = {10.1145/0000000.0000000},
       publisher = {ACM},
     }
     ```

   - Every `\cite{key}` in `{paths.paper_dir}/background.tex` must have a corresponding entry in `{paths.bib}`.

9. **Report to the user.** Print a summary: number of subsections written, approximate word count of `{paths.paper_dir}/background.tex`, number of citations used, and how many BibTeX entries were newly created vs. reused. List the citation keys for reference.
