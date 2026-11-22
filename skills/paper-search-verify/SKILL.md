---
name: paper-search-verify
description: Audit every paper in the Obsidian paper vault: fill missing abstracts, correct full and short venue names, and flag papers whose Relevance note disagrees with their content
---

# /paper-writer:paper-search-verify

Audit all paper files in the Obsidian paper vault at `vault/paper-writer/`. Fills missing abstracts, verifies and corrects venue names (full and short), and flags papers whose content disagrees with their current Relevance note.

The vault layout is documented in `vault/paper-writer/Vault Layout.md`. Paper files live at the vault root; each contains a `- **DOI**:` line, an `## Abstract` section, and a `## Relevance` section. Topic files (with `## Subtopics` or `## Papers`) are **not** audited — only paper files.

This skill never reads or writes the legacy `search-results/` folder.

## Steps

1. **Discover all paper files in the vault.** Run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" vault list_paper_files
   ```

   This prints the path of every `.md` file in `vault/paper-writer/` that has a DOI line (i.e., is a paper file rather than a topic file or vault metadata file).

2. **Extract DOIs from each paper file.** For each file from step 1, use Read to load the top ~40 lines and parse:
   - DOI (from the `- **DOI**: https://doi.org/...` line, or `- **DOI**: Not available`)
   - Current Venue line (from the `- **Venue**: ...` line)
   - Whether the `## Abstract` section body is non-empty and is not `Not available`

   Build a list `{doi → {path, current_venue, has_abstract}}`. Papers with no DOI are skipped by the S2 lookup step but still reported. Deduplicate by DOI across any accidental duplicate files.

   Report the total number of paper files, number with DOIs, number missing abstracts, and number without DOIs.

3. **Fan out metadata lookups on Semantic Scholar.** Batch DOIs into groups of up to 20. Launch one **Sonnet** Agent per batch, **all in parallel in a single message**. Use `model: "sonnet"` for each agent. Each agent receives this prompt with its batch of DOIs substituted:

   > You are a metadata lookup agent. For each DOI below, retrieve the abstract, full venue name, and year from Semantic Scholar. Run:
   >
   > ```bash
   > python3 << 'PYEOF'
   > import json, subprocess, time
   >
   > dois = {doi_list_as_python_list}
   >
   > results = {}
   > for doi in dois:
   >     try:
   >         url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=abstract,venue,year,publicationVenue"
   >         result = subprocess.run(["curl", "-s", url], capture_output=True, text=True)
   >         data = json.loads(result.stdout)
   >
   >         if data.get("error"):
   >             results[doi] = {"status": "NOT_FOUND"}
   >             time.sleep(1.2)
   >             continue
   >
   >         pub_venue = data.get("publicationVenue") or {}
   >         venue_full = pub_venue.get("name", "") or data.get("venue", "")
   >         year = str(data.get("year", "") or "")
   >         abstract = data.get("abstract", "") or ""
   >
   >         results[doi] = {
   >             "status": "FOUND",
   >             "abstract": abstract,
   >             "venue_full": venue_full,
   >             "year": year,
   >         }
   >     except (json.JSONDecodeError, KeyError):
   >         results[doi] = {"status": "ERROR", "error": "JSON decode failed"}
   >     time.sleep(1.2)
   >
   > print(json.dumps(results, indent=2))
   > PYEOF
   > ```
   >
   > After running the script, report the JSON results back verbatim.

4. **Collect results and build a canonical metadata map.** After all batches complete, parse the JSON outputs and assemble `{doi → {abstract, venue_full, venue_short, year}}`:
   - `abstract`: from S2. Use `""` if empty.
   - `venue_full`: from `publicationVenue.name` or `venue`.
   - `venue_short`: apply the SHORT_NAMES mapping (same as in `paper-search`) against `venue_full`, then append the year (e.g., `SIGCOMM 2024`). Empty if no match.

   **Venue verification rules** — cross-check and correct short names:
   - Workshops should carry the workshop's own abbreviation (e.g., "SIGCOMM Workshop on Hot Topics in Networks" → "HotNets", not "SIGCOMM").
   - If the short name does not plausibly match the full name, correct it using the parenthetical abbreviation or the actual conference name.
   - Common corrections: "Internet Measurement Conference" → "IMC" (not "SIGCOMM"), "Hot Topics in Networks" → "HotNets", workshops with "(GC Wkshps)" → "GLOBECOM Workshops", workshops with "(ICC Workshops)" → "ICC Workshops".

5. **Fan out file update agents — one Sonnet agent per paper file that needs changes**, all in parallel in a single message. A paper file needs changes if any of the following is true:
   - Its abstract section is empty or `Not available` and S2 has an abstract.
   - The S2 venue differs from the current `- **Venue**:` line.
   - The corrected short venue name differs from what is already in the line.

   Skip files that don't need any change. Each agent receives:

   > You are a file update agent. Your task is to update the paper vault file at **{file_path}** with corrected metadata from Semantic Scholar.
   >
   > Here is the canonical metadata for this DOI:
   >
   > ```json
   > {"doi": "...", "venue_full": "...", "venue_short": "...", "year": "...", "abstract": "..."}
   > ```
   >
   > **Step 1: Read the file** with the Read tool. The file follows this shape:
   >
   > ```markdown
   > # {Title}
   >
   > - **DOI**: https://doi.org/{doi}
   > - **Authors**: {authors}
   > - **Year**: {year}
   > - **Venue**: {venue}
   >
   > ## Abstract
   >
   > {abstract body or "Not available"}
   >
   > ## Relevance
   >
   > {relevance text}
   > ```
   >
   > **Step 2: Apply edits** using the Edit tool:
   >
   > - **Venue line:** replace the `- **Venue**:` line with `- **Venue**: {venue_full} ({venue_short})`. If `venue_short` is empty, write just `- **Venue**: {venue_full}` without parentheses.
   > - **Abstract section:** if the current body under `## Abstract` is empty, only whitespace, or the literal `Not available`, replace it with the new abstract. Otherwise leave it alone.
   > - **Year line:** only update if it currently says `Unknown` and the metadata has a year.
   > - **Preserve** the Title, DOI, Authors, and Relevance sections unless the Relevance review below flags a problem.
   >
   > **Step 3: Relevance review.** If the abstract is now available (either from the metadata or already present), compare it against the current `## Relevance` text:
   > - If the abstract confirms the paper is relevant and the current relevance is accurate, leave it alone.
   > - If the abstract reveals a more precise connection, you may refine the relevance text (1–3 sentences, focused).
   > - If the abstract reveals the paper is **not** actually relevant to any of the leaf topics it's attached to, prepend `[FLAGGED - may not be relevant]` to the relevance text and add a brief note explaining what the paper actually covers.
   > - If the abstract is still not available, leave the relevance text alone.
   >
   > **Step 4: Return a short summary** of which fields were changed in this file.

6. **Report** to the user:
   - Total paper files audited.
   - How many had missing abstracts filled in.
   - How many had venue names corrected.
   - How many had relevance text updated or flagged.
   - Any DOIs that could not be resolved on Semantic Scholar (S2 `NOT_FOUND` / `ERROR`).
   - Any paper files without a DOI that were skipped from the S2 lookup.
