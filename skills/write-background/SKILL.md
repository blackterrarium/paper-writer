---
name: write-background
description: Write the background section for the paper
---

# Paper background writing

## Overview

Write the "Background and Motivation" section of an academic paper in LaTeX, given an outline describing the topic background and motivation challenges. You are a professor of computer science and engineering writing for a top conference in your field. Provide comprehensive background context and clearly articulate each motivation challenge in its own paragraph. Do not ramble.

Takes an outline as input (text or file path in `$ARGUMENTS`). Reads the writing style guide, search results referenced in the outline, and the LaTeX template. Writes output to `paper/background.tex` (overwriting if it already exists) and creates or updates `paper/ref.bib`.

**Strict adherence to `guidelines/style.md` is mandatory and non-negotiable.** Every sentence produced by this skill must conform to the style guide's voice, vocabulary, rhythm, paragraph structure, and anti-patterns. A draft that violates the guide's anti-patterns is a defect, not an acceptable output. The style guide must be considered for every word, every sentence, every paragraph — not just loaded once and forgotten.

## Steps

1. **Parse the outline.** Extract the outline from `$ARGUMENTS`. If it looks like a file path (contains `/` or ends in `.md` or `.txt`), read it with Read. Otherwise treat the argument text as the outline itself. Check whether the outline specifies a page length instruction (e.g., "Length: 1.5 pages" or similar). If present, use that target length. Otherwise default to approximately 1 page (~600-800 words for ACM two-column format). Also check whether the outline specifies a custom section title; if not, use "Background and Motivation."

2. **Validate prerequisites.** Use Bash to check that the `template/` directory exists: `test -d template && echo OK || echo MISSING`. If MISSING, print an error telling the user the LaTeX template directory is required, and **stop**. Then verify the outline contains at least one of: a Background subsection or a Motivation subsection. If neither is present, print an error and **stop**.

3. **Set up system name commands.** Run `/paper-writer:paper-name` (follow the steps in that skill) to extract the system name from `paper/main.tex` and ensure the LaTeX name commands (`\name`, `\names`, `\boldname`, `\bigname`) are defined. This also writes `guidelines/name-commands.md` with prompt instructions for the writing agent.

4. **Read shared context.** Read the following files. These will be passed to sub-agents in later steps.

   - Use Read to load `guidelines/style.md`. This guide is the **binding style contract** for every sentence this skill produces — voice, sentence rhythm, vocabulary, connectors, paragraph structure, and anti-patterns. All prose written in later steps must conform to this guide without exception. **If the file does not exist, print an error stating that `guidelines/style.md` is a required prerequisite for style-compliant prose and stop.** Do not fall back to any other style rules and do not proceed without it.
   - Use Read to load the first 120 lines of `template/sample-sigconf-authordraft.tex`. Confirm the template uses `\bibliographystyle{ACM-Reference-Format}` and `\bibliography{...}`. Also use Read to examine `template/sample-base.bib` (first 80 lines) to understand the expected BibTeX entry format.
   - Use Bash: `mkdir -p paper && test -f paper/ref.bib && echo EXISTS || echo NEW`. If it exists, use Read to load its contents. Parse existing BibTeX keys and DOIs so they can be reused rather than duplicated.
   - Use Read to load `guidelines/name-commands.md`. This will be included in the Opus writing prompt.

5. **Select citations.** Parse the outline to identify contexts where citations are needed (marked by "Citation required" or similar pointers, or by explicit paper title references in backticks or brackets). For each citation context, determine the criteria type:

   - For Background contexts (providing supporting evidence, examples, or technical details about the topic): create a context with `CRITERIA: reason`, using the background topic as the label, the relevant description from the outline as the description, and the search result file paths referenced by that context.
   - For Motivation contexts (identifying limitations and challenges with existing approaches): create a context with `CRITERIA: gap`, using each motivation challenge as the label, the challenge description as the description, and the search result file paths referenced by that context.

   Launch one **Sonnet** Agent per citation context, **all in parallel in a single message**. Use `model: "sonnet"` for each agent. Use the prompt templates from `/paper-writer:find-citations` step 3 (the `reason` template for background contexts, the `gap` template for motivation contexts), substituting the context-specific values. Each agent selects 2-4 papers.

6. **Collect citations and assign BibTeX keys.** Follow the `/paper-writer:find-citations` deduplication and key assignment process (step 4 of that skill). Deduplicate by DOI. Assign `AuthorYY` format keys, reusing existing keys from `paper/ref.bib` where DOIs match. Resolve collisions with lowercase letter suffixes (e.g., `Cao21a`, `Cao21b`).

   Build a **citation plan**: a mapping of each background topic and motivation challenge to its citation keys, plus the full BibTeX metadata for each paper.

7. **Write the complete Background and Motivation section.** Use Bash to run `mkdir -p paper`. Launch a single **Opus** Agent with `model: "opus"` to write the entire section. Provide this prompt:

   > You are writing the Background and Motivation section of an academic paper targeting a top systems conference (e.g., ACM SIGCOMM, ASPLOS, OSDI). Write the complete section as a single, coherent piece.
   >
   > **Full outline:**
   > {Paste the complete outline text}
   >
   > **Citation plan:**
   > {For each background topic, list: topic label, and for each citation: BibTeX key, paper title, and the 1-sentence reason from step 4}
   > {For each motivation challenge, list: challenge label, and for each citation: BibTeX key, paper title, and the 1-sentence gap description from step 4}
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
   > - **The style guide's anti-patterns are authoritative.** Every phrase, construction or pattern it forbids is forbidden without exception. Do not rely on memory: consult the pasted guide directly. If unsure whether a phrase is allowed, rewrite without it.
   > - **Self-check before output.** Before producing the final LaTeX, mentally walk through the draft once and verify: (a) no anti-pattern from the style guide appears anywhere; (b) connectors and vocabulary follow the guide; (c) every paragraph opens with a topic sentence, not wind-up. If any check fails, rewrite the offending paragraph before outputting.
   > - If the style guide calls for bold-label paragraph openers, use `\textbf{Label.}` followed by the paragraph text.
   > - Declarative subsection headers that state conclusions, per the style guide's Background/Motivation pattern.
   > - Every `\cite{key}` must use a key from the citation plan above.
   > - Impersonal citation style: never refer to cited papers by author name. State the finding directly and attach the citation.
   > - Target length: {target_length}. Adjust proportionally if a different page length was specified.
   > - The section should earn the solution by demonstrating why the problem is hard, following the "rule out the obvious" pattern from the style guide.
   >
   > Output ONLY the LaTeX content starting with `\section{...}`. No preamble, no explanation.

   Use Write to create `paper/background.tex` with the agent's output.

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

   - Every `\cite{key}` in `paper/background.tex` must have a corresponding entry in `paper/ref.bib`.

9. **Report to the user.** Print a summary: number of subsections written, approximate word count of `paper/background.tex`, number of citations used, and how many BibTeX entries were newly created vs. reused. List the citation keys for reference.
