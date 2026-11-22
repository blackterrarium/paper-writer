---
name: find-citations
description: Select relevant citations from the Obsidian paper vault for any section of an academic paper
---

Select relevant citations from the Obsidian paper vault for any section of an academic paper. Takes citation contexts describing what to cite and why, reads vault paper files under the specified topic subtrees, and produces a citation plan with BibTeX keys. Reusable across introduction, background, related work, or any section needing citations.

Takes citation contexts as input (text or file path in `$ARGUMENTS`). Writes a structured citation plan to a specified output file (default `paper/citation-plan.md`).

The vault layout is documented in `vault/paper-writer/Vault Layout.md`: papers are `.md` files at `vault/paper-writer/`, attached to leaf topics via `[[wikilinks]]`. This skill never reads or writes the legacy `search-results/` folder.

## Input format

The input must contain one or more citation contexts and optionally a bib file path and output path. Each context has a label, description, list of topic files to pull candidate papers from, selection count, and criteria type. Example:

```
BIB FILE: paper/ref.bib
OUTPUT: paper/citation-plan.md

CONTEXT: Challenge 1: Slow convergence of rate control
CRITERIA: reason
SELECT: 2-4
TOPICS:
  - vault/paper-writer/Datacenter Congestion Control.md
  - vault/paper-writer/Transport Performance Measurement.md
DESCRIPTION:
  Window-based senders need several round trips to converge after a
  load change, and queues build up in the meantime. Prior measurements show...
END CONTEXT

CONTEXT: Insufficiency of existing methods
CRITERIA: gap
SELECT: 2-4
TOPICS:
  - vault/paper-writer/Datacenter Transport.md
DESCRIPTION:
  Solution insight: ...
  Challenges being addressed: ...
END CONTEXT
```

`TOPICS:` accepts either leaf topic files or intermediate topic files. For intermediate topics, the skill recursively collects every paper attached to any leaf under that subtree.

## Steps

1. **Parse input.** Extract the input from `$ARGUMENTS`. If it looks like a file path (contains `/` or ends in `.md` or `.txt`), read it with Read. Otherwise treat the argument text as the input itself. Parse all `CONTEXT ... END CONTEXT` blocks. Extract `BIB FILE` (default: `paper/ref.bib`) and `OUTPUT` (default: `paper/citation-plan.md`).

2. **Load existing BibTeX state.** Use Bash: `test -f {bib_file} && echo EXISTS || echo NEW`. If it exists, use Read to load its contents. Parse existing BibTeX keys and DOIs so they can be reused rather than duplicated.

3. **Expand each context's TOPICS to a concrete paper file list.** For each context, for each entry in its `TOPICS:` block, run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" vault papers_under "{topic name}"
   ```

   where `{topic name}` is the topic's file stem (basename without `.md`). This prints the path of every paper file attached to that topic or any leaf underneath it. Deduplicate the combined list for each context. Record the final `{context → [paper_file_paths]}` mapping.

4. **Fan-out: one Sonnet agent per citation context.** Launch one **Sonnet** Agent per context, **all in parallel in a single message**. Use `model: "sonnet"` for each agent. Choose the prompt template based on the context's `CRITERIA` value:

   **For `reason` contexts** — papers that support an argument:

   > You are a citation selection agent for an academic paper. Your task is to select the most relevant papers for a specific citation context.
   >
   > **{context label}**
   > {context description}
   >
   > Read the following vault paper files in full using the Read tool (one file per paper):
   > {list of paper file paths}
   >
   > Select the **{N} most relevant papers** for this context based on:
   > - The paper's `## Abstract` section — this is the ground truth for what the paper is actually about.
   > - The paper's `## Relevance` field describes relevance to the leaf topic(s) it is attached to, not to the citation context. Use it as a hint but not as the deciding signal.
   > - Papers explicitly named by title in the context description above — **always include these**.
   > - Prefer papers from top-tier venues (SIGCOMM, OSDI, NSDI, SOSP, ASPLOS, MobiCom, CoNEXT, EuroSys) — check the `- **Venue**:` line.
   >
   > For each selected paper, output a structured block:
   > ```
   > SELECTED PAPER:
   >   Title: {exact title}
   >   Authors: {full author list as it appears}
   >   Year: {year}
   >   Venue: {full venue name}
   >   DOI: {DOI}
   >   Reason: {1 sentence explaining why this paper supports the argument}
   > ```
   >
   > Select only {N} papers. Be selective — choose papers that directly support the argument, not tangentially related ones.

   **For `gap` contexts** — papers representing existing approaches with limitations:

   > You are a citation selection agent for an academic paper. Your task is to select papers that represent existing approaches which, despite their contributions, fail to fully address the stated needs.
   >
   > **{context label}**
   > {context description}
   >
   > Read the following vault paper files in full using the Read tool (one file per paper):
   > {list of paper file paths}
   >
   > Select **{N} papers** that best represent existing approaches whose limitations motivate the proposed solution. For each candidate paper, read its `## Abstract` section to judge fit — the `## Relevance` field describes relevance to the leaf topics it is attached to, not to this citation context. Good candidates are papers that make genuine contributions but leave a gap:
   > - Propose partial solutions (e.g., address one aspect but not another)
   > - Represent the state of the art that the paper's approach goes beyond
   >
   > For each selected paper, output a structured block:
   > ```
   > SELECTED PAPER:
   >   Title: {exact title}
   >   Authors: {full author list as it appears}
   >   Year: {year}
   >   Venue: {full venue name}
   >   DOI: {DOI}
   >   Gap: {1 sentence explaining what gap this paper leaves that the proposed approach addresses}
   > ```
   >
   > Select only {N} papers. Focus on influential, well-known works whose limitations clearly motivate the new approach.

5. **Collect citations and assign BibTeX keys.** After all citation agents complete, collect all selected papers. Deduplicate by DOI. For each paper:

   - Construct a BibTeX key using the format `AuthorYY` where `Author` is the first author's last name (capitalized, no spaces) and `YY` is the two-digit publication year.
   - If a paper with a matching DOI already exists in the loaded BibTeX file, reuse its existing key.
   - If two keys collide, append a lowercase letter (e.g., `Cao21a`, `Cao21b`).

   Build a **citation plan**: a mapping of each context to its citation keys, plus the full BibTeX metadata for each paper.

6. **Write the citation plan.** Use Bash to run `mkdir -p $(dirname {output_path})`. Write the output file with this structure:

   ```markdown
   # Citation Plan

   ## Citations by Context

   ### {context label 1}
   - \cite{Key1}: {title} — {reason or gap}
   - \cite{Key2}: {title} — {reason or gap}

   ### {context label 2}
   - \cite{Key3}: {title} — {reason or gap}

   ## BibTeX Entries

   @inproceedings{Key1,
     author    = {authors},
     title     = {title},
     booktitle = {full venue name},
     year      = {year},
     doi       = {doi},
     publisher = {ACM or IEEE},
   }

   ...
   ```

   Use `ACM` as publisher for `10.1145` DOIs, `IEEE` for `10.1109` DOIs.

7. **Report to the user.** Print a summary: number of citation contexts processed, total papers selected, unique papers after deduplication, new BibTeX entries vs. reused from existing bib file. List all citation keys for reference.
