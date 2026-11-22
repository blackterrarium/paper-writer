---
name: write-intro
description: Write the introduction section of an academic paper in LaTeX
---

# Paper introduction writing

## Overview

Write the introduction section of an academic paper in LaTeX, given an outline describing front matter, challenges, solutions, and contributions. You are a professor of computer science and engineering writing for a top conference in your field. Aim for more verbose and comprehensive writing while maintaining accuracy and conciseness. Do not ramble.

Takes an outline as input (text or file path in `$ARGUMENTS`). Reads the writing style guide, search results referenced in the outline, and the project's main LaTeX file. Writes output to `{paths.paper_dir}/intro.tex` (overwriting if it already exists) and creates or updates `{paths.bib}`.

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

1. **Parse the outline.** Extract the outline from `$ARGUMENTS`. If it looks like a file path (contains `/` or ends in `.md` or `.txt`), read it with Read. Otherwise treat the argument text as the outline itself.

2. **Validate prerequisites.** Use Bash to check that the paper's main LaTeX file exists: `test -f {paths.main_tex} && echo OK || echo MISSING`. If MISSING, print an error telling the user that `{paths.main_tex}` is required (run `/paper-writer:init` to create a project), and **stop**. Then verify the outline contains all four required subsections: **Front Matter**, **Challenges**, **Solution**, and **Contributions**. If any subsection is missing, print an error listing the missing subsections and **stop**.

3. **Set up system name commands.** Run `/paper-writer:paper-name` (follow the steps in that skill) to extract the system name from `{paths.main_tex}` and ensure the LaTeX name commands (`\name`, `\names`, `\boldname`, `\bigname`) are defined. This also writes `{paths.name_commands}` with prompt instructions for the writing agent.

4. **Read shared context.** Read the following files. These will be passed to sub-agents in later steps.

   - Use Read to load `{style.style_md}`. If `{style.overrides_md}` is set, Read it too: it holds per-project adjustments that take precedence over the guide. Together they are the **binding style contract** for every sentence this skill produces — voice, sentence rhythm, vocabulary, connectors, paragraph structure, and anti-patterns. All prose written in later steps must conform to this guide without exception. Do not fall back to any other style rules.
   - Use Read to load `{paths.main_tex}`. Note its document class, its `\bibliographystyle{...}` and its `\bibliography{...}` file, so the new section and BibTeX entries match them. Use the BibTeX entry format shown in step 8.
   - Use Bash: `mkdir -p {paths.paper_dir} && test -f {paths.bib} && echo EXISTS || echo NEW`. If it exists, use Read to load its contents. Parse existing BibTeX keys and DOIs so they can be reused rather than duplicated.
   - Use Read to load `{paths.name_commands}`. This will be included in the Opus writing prompt.

5. **Select citations.** Parse the outline to identify each challenge and its referenced search results file(s). Also extract the **Solution insight** from the outline. Build citation contexts from the outline:

   - For each challenge: create a context with `CRITERIA: reason`, using the challenge title as the label, the full challenge description (including any papers named by title) as the description, and the search result file paths referenced by that challenge.
   - Create one additional context for "Insufficiency of existing methods" with `CRITERIA: gap`, using the solution insight and a brief summary of all challenges as the description, and ALL search result file paths referenced anywhere in the outline.

   Launch one **Sonnet** Agent per citation context, **all in parallel in a single message**. Use `model: "sonnet"` for each agent. Use the prompt templates from `/paper-writer:find-citations` step 3 (the `reason` template for challenge contexts, the `gap` template for the insufficiency context), substituting the context-specific values. Each agent selects 2-4 papers.

6. **Collect citations and assign BibTeX keys.** Follow the `/paper-writer:find-citations` deduplication and key assignment process (step 4 of that skill). Deduplicate by DOI. Assign `AuthorYY` format keys, reusing existing keys from `{paths.bib}` where DOIs match. Resolve collisions with lowercase letter suffixes (e.g., `Cao21a`, `Cao21b`).

   Build a **citation plan**: a mapping of each challenge (and the insufficiency paragraph) to its citation keys, plus the full BibTeX metadata for each paper.

7. **Write the complete introduction.** Use Bash to run `mkdir -p {paths.paper_dir}`. Launch a single **Opus** Agent with `model: "opus"` to write the entire introduction. Provide this prompt:

   > You are writing the introduction section of an academic paper targeting a top venue in {paper.field} (e.g., {paper.target_venues}). Write the complete introduction as a single, coherent piece.
   >
   > **Paper title:** {title from the outline}
   >
   > **Full outline:**
   > {Paste the complete outline text — front matter, challenges, solutions, and contributions}
   >
   > **Citation plan:**
   > {For each challenge, list: challenge title, and for each citation: BibTeX key, paper title, and the 1-sentence reason from step 4}
   > {For the insufficiency argument, list: and for each citation: BibTeX key, paper title, and the 1-sentence gap description from step 4}
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
   > **Structure — follow this order exactly:**
   >
   > 1. `\section{Introduction}` as the only sectioning command. Do **not** use `\subsection` or any other heading commands. The subsections from the outline are woven into a single coherent flow with no visible sub-headings.
   >
   > 2. **Front matter** (1 paragraph): Set the broad context for the topic, then narrow to the specific problem addressed. This paragraph must naturally lead into the challenges that follow. Do NOT restate the challenges — just set up the context so the reader understands why they matter.
   >
   > 3. **Challenges** (1 paragraph each, in the order they appear in the outline): For each challenge, write a concise paragraph. Open with a topic sentence that names the challenge using bold: `\textbf{challenge title}`. Use `\cite{key}` references where they support the argument. Leave detailed explanations for later sections — be concise but substantive.
   >
   > 4. **Insight** (1 paragraph): Present the high-level insight that motivates the solution approach. This gives context explaining the reason for the selection of the solution components.
   >
   > 5. **Insufficiency of existing methods** (1 paragraph): Argue why existing methods are insufficient. Acknowledge each cited work's contribution, then argue why it leaves a gap given the insight. Use `\cite{key}` references. Build an argument that motivates the need for the proposed solution.
   >
   > 6. **Solution summary** (1-2 sentences at the start of the next paragraph): Enumerate the key features of the solution and emphasize in a single sentence that it is novel in addressing the aforementioned challenges. This summary comes before delving into the details.
   >
   > 7. **Solution details** (1 paragraph per solution): Start each solution point on a separate paragraph. Focus on clear, well-researched arguments about how each solution addresses one or more of the stated challenges. No references are required for solutions.
   >
   > 8. **Reinforcement** (1 short paragraph, 2-3 sentences): After describing all solution points, write a short paragraph reinforcing how the solutions address the challenges smoothly and intuitively.
   >
   > 9. **Contributions** (1+ paragraphs): Provides an overview of the rest of the paper. Start with "We will describe the design and implementation of \name in the rest of this paper to address..." (filling in the system name and challenges from the outline). Include 2-3 word descriptions of each paper section: background and motivation, design of the system, implementation of the system, and evaluation of the system. Describe how the system is implemented and evaluated. Mention evaluation results briefly as stated in the outline.
   >
   > **Rules:**
   > - Follow the writing style guide strictly: its voice, sentence rhythm, clause ordering, vocabulary and paragraph patterns.
   > - **The guide's anti-patterns, the hard-reject list and the forbidden constructions are authoritative.** Every phrase, construction or pattern they name is forbidden without exception. Do not rely on memory: consult the pasted guide and lists directly. If unsure whether a phrase is allowed, rewrite without it.
   > - **Self-check before output.** Before producing the final LaTeX, mentally walk through the draft once and verify: (a) no phrase from the hard-reject list or the guide's anti-patterns appears anywhere; (b) none of the forbidden constructions appears; (c) connectors and vocabulary follow the guide; (d) every paragraph opens with a topic sentence, not wind-up. If any check fails, rewrite the offending paragraph before outputting.
   > - Every `\cite{key}` must use a key from the citation plan above.
   > - Target length: approximately 1200-1500 words (≈1.5-2 pages of two-column conference text). It can be longer but not substantially shorter.
   >
   > Output ONLY the LaTeX content starting with `\section{Introduction}`. No preamble, no explanation.

   Use Write to create `{paths.paper_dir}/intro.tex` with the agent's output.

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

   - Every `\cite{key}` in `{paths.paper_dir}/intro.tex` must have a corresponding entry in `{paths.bib}`.

9. **Report to the user.** Print a summary: number of paragraphs written, approximate word count of `{paths.paper_dir}/intro.tex`, number of citations used, and how many BibTeX entries were newly created vs. reused. List the citation keys for reference.
