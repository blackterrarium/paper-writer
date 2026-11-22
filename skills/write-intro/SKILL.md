---
name: write-intro
description: Write the introduction section of an academic paper in LaTeX
---

# Paper introduction writing

## Overview

Write the introduction section of an academic paper in LaTeX, given an outline describing front matter, challenges, solutions, and contributions. You are a professor of computer science and engineering writing for a top conference in your field. Aim for more verbose and comprehensive writing while maintaining accuracy and conciseness. Do not ramble.

Takes an outline as input (text or file path in `$ARGUMENTS`). Reads the writing style guide, search results referenced in the outline, and the LaTeX template. Writes output to `paper/intro.tex` (overwriting if it already exists) and creates or updates `paper/ref.bib`.

**Strict adherence to `guidelines/style.md` is mandatory and non-negotiable.** Every sentence produced by this skill must conform to the style guide's voice, vocabulary, rhythm, paragraph structure, and anti-patterns. A draft that violates the guide's anti-patterns is a defect, not an acceptable output. The style guide must be considered for every word, every sentence, every paragraph — not just loaded once and forgotten.

## Steps

1. **Parse the outline.** Extract the outline from `$ARGUMENTS`. If it looks like a file path (contains `/` or ends in `.md` or `.txt`), read it with Read. Otherwise treat the argument text as the outline itself.

2. **Validate prerequisites.** Use Bash to check that the `template/` directory exists: `test -d template && echo OK || echo MISSING`. If MISSING, print an error telling the user the LaTeX template directory is required, and **stop**. Then verify the outline contains all four required subsections: **Front Matter**, **Challenges**, **Solution**, and **Contributions**. If any subsection is missing, print an error listing the missing subsections and **stop**.

3. **Set up system name commands.** Run `/paper-writer:paper-name` (follow the steps in that skill) to extract the system name from `paper/main.tex` and ensure the LaTeX name commands (`\name`, `\names`, `\boldname`, `\bigname`) are defined. This also writes `guidelines/name-commands.md` with prompt instructions for the writing agent.

4. **Read shared context.** Read the following files. These will be passed to sub-agents in later steps.

   - Use Read to load `guidelines/style.md`. This guide is the **binding style contract** for every sentence this skill produces — voice, sentence rhythm, vocabulary, connectors, paragraph structure, and anti-patterns. All prose written in later steps must conform to this guide without exception. **If the file does not exist, print an error stating that `guidelines/style.md` is a required prerequisite for style-compliant prose and stop.** Do not fall back to any other style rules and do not proceed without it.
   - Use Read to load the first 120 lines of `template/sample-sigconf-authordraft.tex`. Confirm the template uses `\bibliographystyle{ACM-Reference-Format}` and `\bibliography{...}`. Also use Read to examine `template/sample-base.bib` (first 80 lines) to understand the expected BibTeX entry format.
   - Use Bash: `mkdir -p paper && test -f paper/ref.bib && echo EXISTS || echo NEW`. If it exists, use Read to load its contents. Parse existing BibTeX keys and DOIs so they can be reused rather than duplicated.
   - Use Read to load `guidelines/name-commands.md`. This will be included in the Opus writing prompt.

5. **Select citations.** Parse the outline to identify each challenge and its referenced search results file(s). Also extract the **Solution insight** from the outline. Build citation contexts from the outline:

   - For each challenge: create a context with `CRITERIA: reason`, using the challenge title as the label, the full challenge description (including any papers named by title) as the description, and the search result file paths referenced by that challenge.
   - Create one additional context for "Insufficiency of existing methods" with `CRITERIA: gap`, using the solution insight and a brief summary of all challenges as the description, and ALL search result file paths referenced anywhere in the outline.

   Launch one **Sonnet** Agent per citation context, **all in parallel in a single message**. Use `model: "sonnet"` for each agent. Use the prompt templates from `/paper-writer:find-citations` step 3 (the `reason` template for challenge contexts, the `gap` template for the insufficiency context), substituting the context-specific values. Each agent selects 2-4 papers.

6. **Collect citations and assign BibTeX keys.** Follow the `/paper-writer:find-citations` deduplication and key assignment process (step 4 of that skill). Deduplicate by DOI. Assign `AuthorYY` format keys, reusing existing keys from `paper/ref.bib` where DOIs match. Resolve collisions with lowercase letter suffixes (e.g., `Cao21a`, `Cao21b`).

   Build a **citation plan**: a mapping of each challenge (and the insufficiency paragraph) to its citation keys, plus the full BibTeX metadata for each paper.

7. **Write the complete introduction.** Use Bash to run `mkdir -p paper`. Launch a single **Opus** Agent with `model: "opus"` to write the entire introduction. Provide this prompt:

   > You are writing the introduction section of an academic paper targeting a top systems conference (e.g., ACM SIGCOMM, ASPLOS, OSDI). Write the complete introduction as a single, coherent piece.
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
   > {Paste the full contents of guidelines/name-commands.md}
   >
   > **NON-NEGOTIABLE STYLE CONTRACT — READ THIS BEFORE WRITING ANYTHING:**
   >
   > The writing style guide pasted below is the single source of truth for tone, vocabulary, sentence rhythm, paragraph structure, connectors, and forbidden phrases. It is a binding contract, not a suggestion. Every paragraph, every sentence, every word choice must conform to it. Consider the style guide while writing every sentence — do not load it once and forget it. Before you output the final LaTeX, re-read the guide's anti-patterns and verify that your draft contains none of them. Any violation is a defect that must be rewritten, not shipped.
   >
   > **Writing style (binding contract — violations are defects that must be rewritten):**
   > {Paste the full contents of guidelines/style.md}
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
   > - **The style guide's anti-patterns are authoritative.** Every phrase, construction or pattern it forbids is forbidden without exception. Do not rely on memory: consult the pasted guide directly. If unsure whether a phrase is allowed, rewrite without it.
   > - **Self-check before output.** Before producing the final LaTeX, mentally walk through the draft once and verify: (a) no anti-pattern from the style guide appears anywhere; (b) connectors and vocabulary follow the guide; (c) every paragraph opens with a topic sentence, not wind-up. If any check fails, rewrite the offending paragraph before outputting.
   > - Every `\cite{key}` must use a key from the citation plan above.
   > - Target length: approximately 1200-1500 words (≈1.5-2 pages of ACM SigConf two-column text). It can be longer but not substantially shorter.
   >
   > Output ONLY the LaTeX content starting with `\section{Introduction}`. No preamble, no explanation.

   Use Write to create `paper/intro.tex` with the agent's output.

8. **Write or update `paper/ref.bib`.** Use Write (or Edit if appending to an existing file) to create or update `paper/ref.bib`:

   - If `paper/ref.bib` already existed, preserve all existing entries unchanged. Append new entries at the end.
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

   - Every `\cite{key}` in `paper/intro.tex` must have a corresponding entry in `paper/ref.bib`.

9. **Report to the user.** Print a summary: number of paragraphs written, approximate word count of `paper/intro.tex`, number of citations used, and how many BibTeX entries were newly created vs. reused. List the citation keys for reference.
