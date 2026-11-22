---
name: design-review
description: Critically analyse an implementation and produce a design document detailing innovations, novelty, and how they address paper challenges
---

# Design review

## Overview

Critically analyse the implementation of a system and produce a design document at `design/design-details/` that details the key design contributions, how they are innovative, and how they address the challenges framed in the paper introduction. Every innovation claim must be grounded either in the system's own source/design files or in published related work from the paper vault at `vault/paper-writer/`.

Takes a system location and optional extra instructions as input (`$ARGUMENTS`). Reads architecture/design `.md` files in the target system, extracts challenges and solution framework from `paper/intro.tex`, grounds each innovation against the paper vault (falling back to `/paper-writer:paper-search` when the vault is too thin), and writes an Obsidian-style design document linked from `design/design-details/root.md`.

## Instruction priority

The priority of instructions in this skill, highest to lowest:

1. **User prompt passed to this skill in `$ARGUMENTS`.** These override every other instruction below, including this SKILL.md itself.
2. **`CLAUDE.md` and other project/system-level user prompts.**
3. **Every other system prompt, including the default steps below.**

If the user's prompt in `$ARGUMENTS` conflicts with any step below, follow the user and note the deviation in the final report.

## Steps

1. **Parse arguments.** Extract from `$ARGUMENTS`: (a) the **system directory** to review (an absolute or project-relative path; required), and (b) any extra instructions, focus areas, or design points the user wants emphasised. If the directory is not stated, print an error asking for it and stop. Keep the extra instructions in working context — they take priority over every subsequent step in this skill.

2. **Validate the paper focus file.** The paper introduction is a hard prerequisite. Run:

   ```bash
   test -f paper/intro.tex && echo OK || echo MISSING
   ```

   If MISSING, print a loud error stating that `paper/intro.tex` is required and **stop** without writing any files. Otherwise, use Read to load its full contents.

3. **Extract challenges and solution framework from `paper/intro.tex`.** Pull out, into working memory:
   - The named challenges — typically the lead `\textbf{...}` of each challenge paragraph (e.g., "Deep human expertise", "Low dynamism and adaptability", "Poor accessibility").
   - The solution insight paragraph and the named solution components (e.g., `\textbf{Autonomous Network Construction}`, `\textbf{Autonomous Network Programming}`).
   - The system `\name`.
   - Any specific evaluation claims the intro makes (these bound what the design document can assert).

   **Every design innovation you later claim must tie back to one or more of these challenges.** Innovations that address nothing in the intro do not belong in this document.

4. **Map the file structure of the system under review.** Walk the target system directory with Glob/Bash and enumerate:
   - **Documentation and design files** — any `*.md` file. Prioritize `ARCHITECTURE.md`, `DESIGN.md`, `README.md`, `docs/**/*.md`, `design/**/*.md`.
   - **Source layout** — top-level directories, language, framework/entry points (just enumerate names — do not deep-read code yet).

   If **no architecture or design `.md` files are found** (only README or nothing), print a prominent warning listing exactly what was and was not found, then continue. This is a warning, not a fatal error.

5. **Read the design material.** Use Read to load every architecture/design `.md` file from step 4 in full. Then skim source entry points and top-level directory READMEs only as needed to disambiguate or verify specific design claims. The goal is a concrete, verifiable mental model of the architecture. Do not fabricate details that are not present in the files you read.

6. **Derive the system short name.** Follow the steps in `/paper-writer:paper-name` to extract the `\name` value from `paper/main.tex`. Sanitize it into a filename-safe stem with no spaces (e.g., `Acme`). If `/paper-writer:paper-name` cannot resolve a name, fall back to the basename of the system directory from step 1. Call the result `<SystemName>`. The design document will live at `design/design-details/<SystemName>.md`.

7. **Identify 2–5 candidate design innovations.** Based on steps 3 and 5, draft an internal list of candidate innovations. For each candidate, write down: a short feature name, a one-sentence goal, a crisp claim about *what specifically* is novel, and the challenge(s) from step 3 it addresses. **Prioritize high-impact design points.** Drop any candidate whose novelty claim cannot be stated concretely. Two strong innovations are worth more than five weak ones.

8. **Generate search topics per innovation.** For each candidate, produce 2–3 short topic phrases that describe the innovation well enough to find related work (e.g., "agentic network configuration synthesis", "LLM-driven data-plane policy generation"). These drive both the vault lookup in step 9 and any fallback search in step 10.

9. **Ground each innovation in vault related work.**

   9a. **Load the vault topic tree** to see what leaves exist:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" vault load_tree
   ```

   For each innovation, pick 1–3 existing leaf topic files that best match its search phrases. For each chosen leaf, expand to the concrete paper file list:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" vault papers_under "<topic stem>"
   ```

   Where `<topic stem>` is the filename without `.md`. Deduplicate the combined list per innovation.

   9b. **Fan out Sonnet agents in parallel — one per innovation, all in a single message.** Use `model: "sonnet"` for each. Each agent runs the `gap` selection template (copied from `/paper-writer:find-citations` step 4, adapted to design review):

   > You are a related-work assessor for a design review. Your task is to select **2–4 papers** that best represent existing approaches whose limitations motivate the design innovation below.
   >
   > **Innovation:** {feature name}
   > **Goal:** {one-sentence goal}
   > **Novelty claim:** {what specifically is novel}
   > **Challenges addressed (from the paper intro):** {list of challenges}
   >
   > Read the following vault paper files in full using the Read tool (one file per paper):
   > {list of paper file paths}
   >
   > For each candidate, read its `## Abstract` section to judge fit — `## Relevance` describes relevance to the leaf topic it is attached to, not to this innovation. Good candidates are papers that make genuine contributions but leave a gap the innovation fills:
   > - Propose partial solutions (address one aspect but not another)
   > - Represent the state of the art that this innovation goes beyond
   > - Come from top-tier venues (SIGCOMM, OSDI, NSDI, SOSP, ASPLOS, MobiCom, CoNEXT, EuroSys) where possible — check `- **Venue**:`
   >
   > For each selected paper, output a structured block:
   > ```
   > SELECTED PAPER:
   >   Title: {exact title}
   >   Authors: {full author list as it appears}
   >   Year: {year}
   >   Venue: {full venue name}
   >   DOI: {DOI}
   >   Gap: {1-2 sentences: what this paper does, and what gap it leaves that the innovation fills}
   > ```
   >
   > Select only 2–4 papers. Be strict — tangential matches do not count.

   Collect the `SELECTED PAPER` blocks per innovation.

10. **Expand the vault if an innovation is underfed.** If any innovation returns fewer than **2** usable related papers from step 9b, invoke `/paper-writer:paper-search` (follow the steps in that skill) with the innovation's 2–3 topic phrases. This writes new papers into the vault. Then re-run step 9 **for that innovation only**. Cap the fallback at **one round per innovation** to avoid ballooning scope.

11. **Verification gate — drop the ungrounded.** Every innovation that ships in the design document must point at a concrete related paper whose limitation justifies the novelty claim. If after step 10 an innovation still has zero grounding papers, **drop it from the document**. Never ship an ungrounded innovation. Also drop any claim whose details cannot be traced to (a) a file in the system directory, (b) a line in `paper/intro.tex`, or (c) a cited published paper.

12. **Compose the design document.** Use Bash: `mkdir -p design/design-details`. Then use Write to create `design/design-details/<SystemName>.md` with this structure:

    ```markdown
    # <SystemName> Design Review

    ## Overview

    {2–4 paragraphs summarising the design contributions and the novelty story, explicitly naming the challenges from step 3 and how the surviving innovations map onto them.}

    ## Innovation: <Feature Name 1>

    # <Feature Name 1>

    **Goal:** <one sentence describing what this design point achieves>

    **Innovation:** <how this design feature is innovative vs. prior work>

    **Challenges:** <which challenges from the intro this addresses, and how>

    **Architecture:** <2–3 sentences about the approach>

    **Tech Stack:** <key technologies and libraries>
    ---

    {Expanded prose: how the design actually works, key mechanisms, interfaces, and the data or control flow. Every factual claim must be traceable to a design file, a source file, or a cited paper.}

    ### Related work

    - **<Paper title>** (<Authors>, <Year>, <Venue>). <1–2 sentences: what the paper contributes, and what gap it leaves that this innovation fills.>
    - ...

    ## Innovation: <Feature Name 2>
    ...

    ## References

    - <Paper title>. <Authors>. <Year>. <Venue>. DOI: <doi>.
    - ...
    ```

    **Required header block:** The inner `# <Feature Name>` / `**Goal:**` / `**Innovation:**` / `**Challenges:**` / `**Architecture:**` / `**Tech Stack:**` / `---` block is mandatory verbatim for every innovation — it is the contract with the user for this document type. Use plain Obsidian markdown throughout. Do **not** use LaTeX `\cite` — this is a design note, not paper text.

    **No vagueness.** Every sentence must contain content a professor could use when writing the paper. If a detail is unknown, state so explicitly rather than filling space.

13. **Update `design/design-details/root.md`.** Use Read to load the current contents.
    - **If the file contains only the Obsidian placeholder** (`This is your new *vault*...`) or is empty, use Write to overwrite it with:

      ```markdown
      # Design Details

      ## Systems Reviewed

      - [[<SystemName>]]
      ```

    - **Otherwise**, use Edit to append `- [[<SystemName>]]` under the existing `## Systems Reviewed` heading. If that heading does not exist, add it after the first heading in the file. **Never delete existing links.** If the wikilink already exists, skip the edit.

14. **Report to the user.** Print a structured summary:
    - `<SystemName>` and the path of the generated design document.
    - Count of innovations kept vs. dropped, with a one-line reason for each drop.
    - Per innovation: number of grounding papers and whether they came from the existing vault or from a `/paper-writer:paper-search` fallback.
    - Any architecture/design `.md` files that were missing from the system directory (from step 4's warning).
    - Any deviations from this skill's default steps driven by user instructions in `$ARGUMENTS`.
